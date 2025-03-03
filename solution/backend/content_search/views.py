import json

import requests
from django.conf import settings
from django.db.models import F, Prefetch
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from common.api import OpenApiQueryParameter
from common.functions import establish_client, get_tokens_for_user
from common.mixins import PAGINATION_PARAMS, OptionalPaginationMixin
from file_manager.models import AbstractRepoCategory, DocumentType, Subject
from resources.models import AbstractCategory, AbstractLocation
from resources.views.mixins import LocationExplorerViewSetMixin

from .models import ContentIndex
from .serializers import ContentListSerializer, ContentSearchSerializer, ContentUpdateSerializer


class ContentSearchViewset(LocationExplorerViewSetMixin, OptionalPaginationMixin, viewsets.ReadOnlyModelViewSet):
    model = ContentIndex
    queryset = ContentIndex.objects.all()
    paginate_by_default = True
    location_filter_prefix = "locations__"
    pagination_class = OptionalPaginationMixin.pagination_class

    @extend_schema(
        description="Retrieve list of uploaded files",
        parameters=[
                    OpenApiQueryParameter("category_details",
                                          "Specify whether to show details of a category, or just the ID.",
                                          bool, False),
                    OpenApiQueryParameter("location_details",
                                          "Specify whether to show details of a location, or just the ID.",
                                          bool, False),
                    OpenApiQueryParameter("document-type",
                                          "Limit results to only resources found within this category. Use "
                                          "\"&document-type=X\"", int, False),
                    OpenApiQueryParameter("subjects",
                                          "Limit results to only resources found within these subjects. Use "
                                          "\"&subjects=X&subjects=Y\" for multiple.", str, False),
                    OpenApiQueryParameter("q",
                                          "Search for text within file metadata. Searches document name, file name, "
                                          "date, and summary/description.", str, False),
                    OpenApiQueryParameter("resource-type",
                                          "Limit results to only resources found within this resource type.  Internal, External,"
                                          "all. Use \"&resource-type=external\"", str, ''),
                    ] + LocationExplorerViewSetMixin.PARAMETERS + OptionalPaginationMixin.PARAMETERS + PAGINATION_PARAMS
    )
    def list(self, request):
        locations = self.request.GET.getlist("locations")
        subjects = self.request.GET.getlist("subjects")
        document_type = self.request.GET.getlist("document-type")
        category = self.request.GET.getlist("category")
        resource_type = self.request.GET.get("resource-type")
        search_query = self.request.GET.get("q")
        paginate = self.request.GET.get("paginate") != 'false'
        query = self.queryset
        q_obj = self.get_location_filter(locations)
        if q_obj:
            query = query.filter(q_obj)
        if subjects:
            if subjects[0] == 'all':
                query = query.filter(subjects__isnull=False)
            else:
                query = query.filter(subjects__id__in=subjects)
        if category:
            query = query.filter(category__id=category)
        if document_type:
            query = query.filter(document_type__id=document_type)
        locations_prefetch = AbstractLocation.objects.all().select_subclasses()
        doc_type_prefetch = DocumentType.objects.all()
        subjects_prefetch = Subject.objects.all()
        category_prefetch = AbstractCategory.objects.all().select_subclasses().select_related("subcategory__parent")
        repo_category_prefetch = AbstractRepoCategory.objects.all().select_subclasses()\
                                                     .select_related("repositorysubcategory__parent")

        # If they are not authenticated they csan only get 'external' documents
        if not request.user.is_authenticated or resource_type == 'external':
            query = query.filter(resource_type='external')
        elif resource_type == 'internal':
            query = query.filter(resource_type='internal')

        context = self.get_serializer_context()
        context['content_id'] = True
        query = query.prefetch_related(
            Prefetch("locations", queryset=locations_prefetch),
            Prefetch("subjects", queryset=subjects_prefetch),
            Prefetch("category", queryset=category_prefetch),
            Prefetch("document_type", queryset=doc_type_prefetch),
            Prefetch("upload_category", queryset=repo_category_prefetch)).distinct()
        if search_query:
            query = query.search(search_query)
        else:
            query = query.order_by(F('date_string').desc(nulls_last=True), F('doc_name_string').asc(nulls_last=True))
        if paginate:
            query = self.paginate_queryset(query)
        context = self.get_serializer_context()
        if search_query:
            serializer = ContentSearchSerializer(query, many=True, context=context)
        else:
            serializer = ContentListSerializer(query, many=True, context=context)
        if paginate:
            return self.get_paginated_response(serializer.data)
        else:
            return Response(serializer.data)


class PostContentTextViewset(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @extend_schema(
        description="Adds text to the content of an index.",
        request=ContentUpdateSerializer,
        responses={200: ContentUpdateSerializer}
    )
    def post(self, request, *args, **kwargs):
        post_data = request.data
        id = post_data['id']
        text = post_data['text']
        index = ContentIndex.objects.get(uid=id)
        index.content = text
        index.save()
        return Response(data=f'Index was updated for {index.doc_name_string}')


class InvokeTextExtractorViewset(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description="Post to the lambda function",
    )
    def get(self, request, *args, **kwargs):
        token = get_tokens_for_user(request.user)['access']
        uid = kwargs.get("content_id")

        if not settings.USE_LOCAL_TEXTRACT:
            post_url = request.build_absolute_uri(reverse("post-content"))
        else:
            post_url = "http://host.docker.internal:8000" + reverse("post-content")
        index = ContentIndex.objects.get(uid=uid)
        if not index:
            return Response({'message': "Index does not exist"})
        json_object = {
            'id': uid,
            'uri': index.url,
            'post_url': post_url,
            'token': token,
        }
        if index.file:
            try:
                json_object['uri'] = index.file.get_key()
                json_object['backend'] = 's3'
                # The lambda already has permissions to access the S3 bucket.  Only on a local run do we pass the keys.
                if settings.USE_LOCAL_TEXTRACT:
                    json_object["aws"] = {
                                            "aws_access_key_id": settings.S3_AWS_ACCESS_KEY_ID,
                                            "aws_secret_access_key": settings.S3_AWS_SECRET_ACCESS_KEY,
                                            "aws_storage_bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
                                            'use_lambda': False,
                                            'aws_region': 'us-east-1'
                                        }
                else:
                    json_object["aws"] = {
                                            'use_lambda': True,
                                            "aws_storage_bucket_name": settings.AWS_STORAGE_BUCKET_NAME,
                                        }
            except ValueError:
                json_object['backend'] = 'web'

        if settings.USE_LOCAL_TEXTRACT:
            # return Response(json_object)
            docker_url = 'http://host.docker.internal:8001/'
            resp = requests.post(
                docker_url,
                data=json.dumps(json_object),
                timeout=60,
            )
            resp.raise_for_status()
        else:
            if settings.TEXT_EXTRACTOR_ARN:
                textract_arn = settings.TEXT_EXTRACTOR_ARN
            else:
                textract_arn = settings.TEXTRACT_ARN
            lambda_client = establish_client('lambda')
            resp = lambda_client.invoke(FunctionName=textract_arn,
                                        InvocationType='Event',
                                        Payload=json.dumps(json_object))
        return Response(data={'response': resp})


class EditContentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description="redirects to a resource of an index.",
    )
    def get(self, request, *args, **kwargs):
        id = kwargs.get("resource_id")
        index = ContentIndex.objects.get(id=id)
        obj = None

        if index.file is not None:
            obj = index.file

        elif index.supplemental_content is not None:
            obj = index.supplemental_content

        elif index.fr_doc is not None:
            obj = index.fr_doc

        if obj is not None:
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.id])
            return redirect(url)
        else:
            return HttpResponseBadRequest("Invalid index - no associated file, supplemental content, or fr_doc.")
