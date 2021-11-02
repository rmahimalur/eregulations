# Generated by Django 3.2.7 on 2021-10-05 19:06

import django.core.validators
from django.db import migrations, models
from django.db.migrations.operations.fields import RemoveField
import django.db.models.deletion
from supplemental_content.models import AbstractModel


def make_category(id, title, description, order):
    return {
        "id": id,
        "title": title,
        "description": description,
        "order": order,
        "children": [],        
    }


def migrate_categories(apps, schema_editor):
    OldCategory = apps.get_model("supplemental_content", "OldCategory")
    Category = apps.get_model("supplemental_content", "Category")
    SubCategory = apps.get_model("supplemental_content", "SubCategory")

    # no cases of 3-level depth before now, so deal with 2 levels only
    old_categories = OldCategory.objects.all()
    parent_categories = [i for i in old_categories if i.parent is None]
    child_categories = [i for i in old_categories if i.parent is not None]
    new_categories = {}

    # construct tree of old parent categories
    for category in parent_categories:
        new_categories[category.id] = make_category(
            category.id, category.title, category.description, category.order
        )
    # append child categories
    for child in child_categories:
        try:
            new_categories[child.parent.id]["children"].append(make_category(
                child.id, child.title, child.description, child.order
            ))
        except KeyError:
            pass
    
    # create new category objects
    for category in list(new_categories.values()):
        parent = Category.objects.create(
            old_id=category["id"],
            name=category["title"],
            description=category["description"],
            order=category["order"],
        )
        for child in category["children"]:
            SubCategory.objects.create(
                old_id=child["id"],
                name=child["title"],
                description=child["description"],
                order=child["order"],
                parent=parent,
            )


def migrate_sections(apps, schema_editor):
    OldRegulationSection = apps.get_model("supplemental_content", "OldRegulationSection")
    Section = apps.get_model("supplemental_content", "Section")
    for section in OldRegulationSection.objects.all():
        Section.objects.create(
            title=int(section.title),
            part=int(section.part),
            section_id=int(section.section),
            old_id=section.id,
        )


def migrate_supplemental_content(apps, schema_editor):
    OldSupplementaryContent = apps.get_model("supplemental_content", "OldSupplementaryContent")
    SupplementalContent = apps.get_model("supplemental_content", "SupplementalContent")
    AbstractCategory = apps.get_model("supplemental_content", "AbstractCategory")
    Section = apps.get_model("supplemental_content", "Section")

    for content in OldSupplementaryContent.objects.all():
        # acquire category from old ID
        new_category = None
        try:
            if content.category:
                new_category = AbstractCategory.objects.filter(old_id=content.category.id)[0]
        except IndexError:
            pass
        
        # acquire list of sections from old ID's
        new_sections = []
        if content.sections:
            for section in content.sections.all():
                try:
                    new_sections.append(
                        Section.objects.filter(old_id=section.id)[0]
                    )
                except IndexError:
                    pass

        # build new supplemental content object
        new_content = SupplementalContent.objects.create(
            name=content.title,
            description=content.description,
            url=content.url,
            date=content.date,
            approved=content.approved,
            created_at=content.created_at,
            updated_at=content.updated_at,
            category=new_category,
        )
        new_content.locations.set(new_sections)
        new_content.save()


class Migration(migrations.Migration):

    dependencies = [
        ('supplemental_content', '0007_auto_20210831_1612'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Category',
            new_name='OldCategory',
        ),
        migrations.RenameModel(
            old_name='RegulationSection',
            new_name='OldRegulationSection',
        ),
        migrations.RenameModel(
            old_name='SupplementaryContent',
            new_name='OldSupplementaryContent',
        ),
        migrations.CreateModel(
            name='AbstractCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=512, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('order', models.IntegerField(blank=True, default=0)),
                ('show_if_empty', models.BooleanField(default=False)),
                ('old_id', models.IntegerField()),
            ],
            bases=(models.Model, AbstractModel),
        ),
        migrations.CreateModel(
            name='AbstractLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.IntegerField()),
                ('part', models.IntegerField()),
            ],
            bases=(models.Model, AbstractModel),
        ),
        migrations.CreateModel(
            name='AbstractSupplementalContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved', models.BooleanField(default=False)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supplemental_content', to='supplemental_content.abstractcategory')),
                ('locations', models.ManyToManyField(blank=True, null=True, related_name='supplemental_content', to='supplemental_content.AbstractLocation')),
            ],
            bases=(models.Model, AbstractModel),
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('abstractcategory_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractcategory')),
            ],
            options={
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
            bases=('supplemental_content.abstractcategory',),
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('abstractlocation_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractlocation')),
                ('section_id', models.IntegerField()),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='supplemental_content.abstractlocation')),
                ('old_id', models.IntegerField()),
            ],
            options={
                'verbose_name': 'Section',
                'verbose_name_plural': 'Sections',
            },
            bases=('supplemental_content.abstractlocation',),
        ),
        migrations.CreateModel(
            name='SubCategory',
            fields=[
                ('abstractcategory_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractcategory')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sub_categories', to='supplemental_content.category')),
            ],
            options={
                'verbose_name': 'Sub-category',
                'verbose_name_plural': 'Sub-categories',
            },
            bases=('supplemental_content.abstractcategory',),
        ),
        migrations.CreateModel(
            name='SubjectGroup',
            fields=[
                ('abstractlocation_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractlocation')),
                ('subject_group_id', models.CharField(max_length=512)),
            ],
            options={
                'verbose_name': 'Subject Group',
                'verbose_name_plural': 'Subject Groups',
            },
            bases=('supplemental_content.abstractlocation',),
        ),
        migrations.CreateModel(
            name='Subpart',
            fields=[
                ('abstractlocation_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractlocation')),
                ('subpart_id', models.CharField(max_length=12)),
            ],
            options={
                'verbose_name': 'Subpart',
                'verbose_name_plural': 'Subparts',
            },
            bases=('supplemental_content.abstractlocation',),
        ),
        migrations.CreateModel(
            name='SubSubCategory',
            fields=[
                ('abstractcategory_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractcategory')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sub_sub_categories', to='supplemental_content.subcategory')),
            ],
            options={
                'verbose_name': 'Sub-sub-category',
                'verbose_name_plural': 'Sub-sub-categories',
            },
            bases=('supplemental_content.abstractcategory',),
        ),
        migrations.CreateModel(
            name='SupplementalContent',
            fields=[
                ('abstractsupplementalcontent_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='supplemental_content.abstractsupplementalcontent')),
                ('name', models.CharField(blank=True, max_length=512, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('url', models.URLField(blank=True, max_length=512, null=True)),
                ('date', models.CharField(blank=True, help_text='Leave blank or enter one of: "YYYY", "YYYY-MM", or "YYYY-MM-DD".', max_length=10, null=True, validators=[django.core.validators.RegexValidator(message='Date field must be blank or of format "YYYY", "YYYY-MM", or "YYYY-MM-DD"! For example: 2021, 2021-01, or 2021-01-31.', regex='^\\d{4}((-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]))|(-(0[1-9]|1[0-2])))?$')])),
            ],
            options={
                'verbose_name': 'Supplemental Content',
                'verbose_name_plural': 'Supplemental Content',
            },
            bases=('supplemental_content.abstractsupplementalcontent',),
        ),
        migrations.RunPython(migrate_sections),
        migrations.RunPython(migrate_categories),
        migrations.RunPython(migrate_supplemental_content),
        migrations.AlterModelOptions(
            name='section',
            options={'ordering': ['title', 'part', 'section_id'], 'verbose_name': 'Section', 'verbose_name_plural': 'Sections'},
        ),
        migrations.AlterModelOptions(
            name='subjectgroup',
            options={'ordering': ['title', 'part', 'subject_group_id'], 'verbose_name': 'Subject Group', 'verbose_name_plural': 'Subject Groups'},
        ),
        migrations.AlterModelOptions(
            name='subpart',
            options={'ordering': ['title', 'part', 'subpart_id'], 'verbose_name': 'Subpart', 'verbose_name_plural': 'Subparts'},
        ),
        migrations.AlterModelOptions(
            name='abstractlocation',
            options={'ordering': ['title', 'part', 'section__section_id', 'subpart__subpart_id', 'subjectgroup__subject_group_id']},
        ),
        migrations.RemoveField(
            model_name='AbstractCategory',
            name='old_id',
        ),
        migrations.RemoveField(
            model_name='Section',
            name='old_id',
        ),
        migrations.AlterUniqueTogether(
            name='oldregulationsection',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='oldregulationsection',
            name='supplementary_content',
        ),
        migrations.RemoveField(
            model_name='oldsupplementarycontent',
            name='category',
        ),
        migrations.DeleteModel(
            name='OldCategory',
        ),
        migrations.DeleteModel(
            name='OldRegulationSection',
        ),
        migrations.DeleteModel(
            name='OldSupplementaryContent',
        ),
    ]