from django.db import models

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import (
    SearchVector,
    SearchVectorField,
    SearchQuery,
    SearchRank,
    SearchHeadline,
)

from regcore.models import Part


class SearchIndexQuerySet(models.QuerySet):
    def effective(self, date):
        return self.filter(part__in=models.Subquery(Part.objects.effective(date.today()).values("id")))

    def search(self, query):
        return self\
            .filter(search_vector=SearchQuery(query))\
            .annotate(rank=SearchRank("search_vector", SearchQuery(query)))\
            .annotate(
                headline=SearchHeadline(
                    "content",
                    SearchQuery(query),
                    start_sel='<span class="search-highlight">',
                    stop_sel='</span>',
                ),
            )\
            .order_by('-rank')\
            .prefetch_related('part')


class SearchIndexManager(models.Manager.from_queryset(SearchIndexQuerySet)):
    pass


class SearchIndex(models.Model):
    type = models.CharField(max_length=32)
    label = ArrayField(base_field=models.CharField(max_length=32))
    content = models.TextField()
    parent = models.JSONField(null=True)
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    search_vector = SearchVectorField()

    objects = SearchIndexManager()

    class Meta:
        unique_together = ['label', 'part']


def create_search(part, piece, memo, parent=None, ):
    if piece.get("node_type", None) == "SECTION":
        si = SearchIndex(
            label=piece["label"],
            part=part,
            parent=piece,
            type=piece["node_type"],
            content=piece.get("title", piece.get("text", "")),
        )
        children = piece.pop("children", []) or []
        for child in children:
            si.content = si.content + child.get("text", "")
        memo.append(si)
    else:
        children = piece.pop("children", []) or []
        for child in children:
            create_search(part, child, memo, parent=piece)

    return memo


def update_search(sender, instance, created, **kwargs):
    SearchIndex.objects.filter(part=instance).delete()
    contexts = create_search(instance, instance.document, [])
    SearchIndex.objects.bulk_create(contexts, ignore_conflicts=True)
    SearchIndex.objects.filter(part=instance).update(search_vector=SearchVector('content'))