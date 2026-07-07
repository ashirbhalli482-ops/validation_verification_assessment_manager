from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from core.models import (
    CustomUser, Company, PackageTemplate, SubPackage, FormDefinition,
    PackageAuthorization, PackageInstance, AuthorizedForm, AuthorizedLibraryDocument,
    LibraryDocument, DropdownList, DropdownOption, Project, TeamMember, EmployeeRecord,
    FormRecord, FormReview, Notification,
)


class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'user_type', 'company', 'is_active']
    list_filter = ['user_type', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('VVB Info', {'fields': ('user_type', 'designation', 'contact_number', 'company', 'under_supervision', 'created_by', 'avatar', 'cv')}),
    )


@admin.register(FormDefinition)
class FormDefinitionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'form_type', 'sub_package', 'created_by', 'order']
    list_filter = ['form_type', 'sub_package']
    search_fields = ['code', 'name', 'description']
    ordering = ['code']


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Company)
admin.site.register(PackageTemplate)
admin.site.register(SubPackage)
admin.site.register(PackageAuthorization)
admin.site.register(PackageInstance)
admin.site.register(AuthorizedForm)
admin.site.register(AuthorizedLibraryDocument)
admin.site.register(LibraryDocument)
admin.site.register(DropdownList)
admin.site.register(DropdownOption)
admin.site.register(Project)
admin.site.register(TeamMember)
admin.site.register(EmployeeRecord)
admin.site.register(FormRecord)
admin.site.register(FormReview)
admin.site.register(Notification)
