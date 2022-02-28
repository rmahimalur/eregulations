# Generated by Django 3.2.12 on 2022-02-23 15:57

from itertools import chain

from django.db import migrations, models


def set_not_null(apps, schema_editor):
    AbstractLocation = apps.get_model("supplemental_content", "AbstractLocation")
    for i in AbstractLocation.objects.all():
        if i.display_name is None:
            i.display_name = ""
            i.save()


def resave_models(apps, schema_editor):
    try:
        from supplemental_content.models import AbstractLocation, AbstractCategory, AbstractSupplementalContent
        for model in chain(AbstractLocation.objects.all(), AbstractCategory.objects.all(), AbstractSupplementalContent.objects.all()):
            model.save()
    except: # Primarily ImportError but safer to catch everything
        pass # Skip in case model is changed, renamed, or deleted in the future


class Migration(migrations.Migration):

    dependencies = [
        ('supplemental_content', '0011_auto_20220211_1139'),
    ]

    operations = [
        migrations.AddField(
            model_name='abstractcategory',
            name='display_name',
            field=models.CharField(max_length=128, blank=True),
        ),
        migrations.AddField(
            model_name='abstractsupplementalcontent',
            name='display_name',
            field=models.CharField(max_length=128, blank=True),
        ),
        migrations.RunPython(set_not_null),
        migrations.AlterField(
            model_name='abstractlocation',
            name='display_name',
            field=models.CharField(max_length=128, blank=True),
        ),
        migrations.RunPython(resave_models),
    ]
