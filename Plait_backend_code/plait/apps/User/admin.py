from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'first_name', 'last_name', 'verified', 'is_allowed',
                    'is_superuser')  # Fields displayed in the list view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'username')}),
        ('Permissions', {'fields': ('verified', 'is_allowed', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
            'email', 'password1', 'password2', 'first_name', 'last_name', 'verified', 'is_allowed', 'is_superuser'),
        }),
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)

    # Define custom actions for the admin panel
    actions = ['delete_selected_custom']

    # Override the default delete_selected action
    def delete_selected_custom(self, request, queryset):
        """
        Custom action to delete selected users
        """
        try:
            # Clear related groups and user permissions
            for user in queryset:
                user.groups.clear()
                user.user_permissions.clear()

            # Delete selected users
            deleted_count, _ = queryset.delete()
            self.message_user(request, f'Successfully deleted {deleted_count} users.')
        except Exception as e:
            self.message_user(request, f'Error deleting users: {str(e)}', level='error')

    delete_selected_custom.short_description = "Delete selected users"


# Register the CustomUser model with the custom admin class
admin.site.register(CustomUser, CustomUserAdmin)
