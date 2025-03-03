from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_jsonform.models.fields import ArrayField
from model_utils.managers import InheritanceManager, InheritanceQuerySet
from solo.models import SingletonModel

from common.fields import (
    NaturalSortField,
    StatuteRefField,
    UscRefField,
    VariableDateField,
)
from common.mixins import DisplayNameFieldMixin


# Field mixins
class InternalNotesFieldMixin(models.Model):
    internal_notes = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True


class TypicalResourceFieldsMixin(InternalNotesFieldMixin):
    name = models.CharField(max_length=512, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    url = models.URLField(max_length=512, null=True, blank=True)
    name_sort = NaturalSortField('name', null=True)
    description_sort = NaturalSortField('description', null=True)
    date = VariableDateField(null=True, blank=True)

    class Meta:
        abstract = True


# Category types
# Current choice is one model per level due to constraint of exactly 2 levels.

class AbstractCategoryQuerySet(InheritanceQuerySet):
    def contains_fr_docs(self):
        return self.annotate(
            is_fr_doc_category=models.ExpressionWrapper(
                ~models.Q(fr_doc_category_config=None),
                output_field=models.BooleanField()
            )
        )


class AbstractCategory(models.Model, DisplayNameFieldMixin):
    name = models.CharField(max_length=512, unique=True)
    description = models.TextField(null=True, blank=True)
    order = models.IntegerField(default=0, blank=True)
    show_if_empty = models.BooleanField(default=False)

    objects = AbstractCategoryQuerySet.as_manager()

    def __str__(self):
        return f"{self.name} ({self._meta.verbose_name})"

    class Meta:
        ordering = ["order", "name"]


class Category(AbstractCategory):

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"


class SubCategory(AbstractCategory):
    parent = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="sub_categories")

    class Meta:
        verbose_name = "Sub-category"
        verbose_name_plural = "Sub-categories"


# Location models
# Defines where supplemental content is located. All locations must inherit from AbstractLocation.


class AbstractLocation(models.Model, DisplayNameFieldMixin):
    title = models.IntegerField()
    part = models.IntegerField()

    objects = InheritanceManager()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["title", "part", "section__section_id", "subpart__subpart_id"]


class Subpart(AbstractLocation):
    subpart_id = models.CharField(max_length=12)

    def __str__(self):
        return f'{self.title} CFR {self.part} Subpart {self.subpart_id}'

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        query = Subpart.objects.filter(title=self.title, part=self.part, subpart_id=self.subpart_id).values_list("id", flat=True)
        if query and self.id not in query:
            raise ValidationError({NON_FIELD_ERRORS: [f"Subpart {str(self)} already exists."]})

    class Meta:
        verbose_name = "Subpart"
        verbose_name_plural = "Subparts"
        ordering = ["title", "part", "subpart_id"]


class Section(AbstractLocation):
    section_id = models.IntegerField()
    parent = models.ForeignKey(AbstractLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="children")

    def __str__(self):
        return f'{self.title} CFR {self.part}.{self.section_id}'

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        query = Section.objects.filter(title=self.title, part=self.part, section_id=self.section_id).values_list("id", flat=True)
        if query and self.id not in query:
            raise ValidationError({NON_FIELD_ERRORS: [f"Section {str(self)} already exists."]})

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        ordering = ["title", "part", "section_id"]


# Resource grouping models


class FederalRegisterDocumentGroup(models.Model):
    docket_number_prefixes = ArrayField(
        models.CharField(max_length=255, blank=True, null=True),
        default=list,
        blank=True,
        help_text="Common prefixes to use when grouping Federal Register Documents, "
                  "e.g. \"CMS-1234-\" to match any docket number starting with that string.",
    )

    def __str__(self):
        prefixes = ", ".join(self.docket_number_prefixes)
        return f"\"{prefixes}\" group"

    class Meta:
        verbose_name = "Federal Register Doc Group"
        verbose_name_plural = "Federal Register Doc Groups"
        ordering = ('docket_number_prefixes',)


# Resource models
# All types of resources must inherit from AbstractResource.


class AbstractResource(models.Model, DisplayNameFieldMixin):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=True)
    category = models.ForeignKey(
        AbstractCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="resources"
    )
    locations = models.ManyToManyField(AbstractLocation, blank=True, related_name="resources")
    related_resources = models.ManyToManyField("self", blank=True, symmetrical=False)
    location_history = models.JSONField(default=list)
    subjects = models.ManyToManyField("file_manager.Subject", blank=True, related_name="resources")

    statute_locations = StatuteRefField(verbose_name="Statute Reference Locations")
    usc_locations = UscRefField(verbose_name="U.S.C. Reference Locations")

    objects = InheritanceManager()


class SupplementalContent(AbstractResource, TypicalResourceFieldsMixin):

    def __str__(self):
        return f"{self.date} {self.name} {self.description[:50]}"

    class Meta:
        ordering = ["-date", "name", "description"]
        verbose_name = "Supplemental Content"
        verbose_name_plural = "Supplemental Content"


doc_types = [('RFI', 'RFI'), ('NPRM', 'NPRM'), ("Final", 'Final')]


class FederalRegisterDocument(AbstractResource, TypicalResourceFieldsMixin):
    docket_numbers = ArrayField(models.CharField(max_length=255, blank=True, null=True), default=list, blank=True)
    document_number = models.CharField(max_length=255, blank=True, null=True)
    correction = models.BooleanField(default=False)
    withdrawal = models.BooleanField(default=False)

    doc_type = models.CharField(
        blank=True,
        max_length=255,
        choices=doc_types,
        default=""
    )

    group = models.ForeignKey(
        FederalRegisterDocumentGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )

    def __str__(self):
        return f"{self.date} {self.document_number}: {self.name}"

    class Meta:
        ordering = ["-date", "document_number", "name", "description"]
        verbose_name = "Federal Register Document"
        verbose_name_plural = "Federal Register Documents"


# Receiver hooks for updating resource groupings on save


def update_related_docs(group_id):
    post_save.disconnect(post_save_fr_doc, sender=FederalRegisterDocument)
    post_save.disconnect(post_save_fr_doc_group, sender=FederalRegisterDocumentGroup)
    docs = FederalRegisterDocument.objects.filter(group=group_id)
    for doc in docs:
        doc.related_resources.set(doc.group.documents.exclude(id=doc.id).order_by("-date"))
        doc.save()
    post_save.connect(post_save_fr_doc, sender=FederalRegisterDocument)
    post_save.connect(post_save_fr_doc_group, sender=FederalRegisterDocumentGroup)


@receiver(post_save, sender=FederalRegisterDocumentGroup)
def post_save_fr_doc_group(sender, instance, **kwargs):
    update_related_docs(instance.id)


@receiver(post_save, sender=FederalRegisterDocument)
def post_save_fr_doc(sender, instance, **kwargs):
    if instance.group:
        update_related_docs(instance.group)


# Singleton model for configuring resources app

class ResourcesConfiguration(SingletonModel):
    fr_doc_category = models.ForeignKey(
        AbstractCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fr_doc_category_config",
        help_text="The category that contains Federal Register Documents. This affects "
                  "all newly uploaded Federal Register Documents.",
    )

    def __str__(self):
        return "Resources Configuration"

    class Meta:
        verbose_name = "Resources Configuration"
