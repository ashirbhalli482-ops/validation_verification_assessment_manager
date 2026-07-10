from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.IndexView.as_view(), name='dashboard'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # User Management
    path('new-user/', views.RegisterView.as_view(), name='new-user'),
    path('users/', views.UsersView.as_view(), name='users'),
    path('team-members/', views.ManagerTeamListView.as_view(), name='team-member-list'),
    path('users/profile', views.ProfileView.as_view(), name='profile'),
    path('users/profile/reset-password/', views.ProfilePasswordResetView.as_view(), name='profile-reset-password'),
    path('users/<int:profile_id>/', views.UserProfileView.as_view(), name='user'),
    path('users/<int:user_id>/edit/', views.EditUserProfileView.as_view(), name='edit-user-profile'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='delete-user'),
    path('users/<int:user_id>/set-password/', views.AdminSetPasswordView.as_view(), name='admin-set-password'),

    # Admin: Companies
    path('admin/companies/', views.CompanyListView.as_view(), name='company-list'),
    path('admin/companies/create/', views.CompanyCreateView.as_view(), name='company-create'),
    path('admin/companies/<int:pk>/', views.CompanyDetailView.as_view(), name='company-detail'),
    path('admin/companies/<int:pk>/edit/', views.CompanyUpdateView.as_view(), name='company-edit'),
    path('admin/companies/<int:pk>/delete/', views.CompanyDeleteView.as_view(), name='company-delete'),

    # Admin: Form Details
    path('admin/form-details/', views.FormDetailsListView.as_view(), name='form-details-list'),
    path('admin/form-details/create/', views.FormDetailsCreateView.as_view(), name='form-details-create'),
    path('admin/form-details/<int:pk>/', views.FormDetailsDetailView.as_view(), name='form-details-detail'),
    path('admin/form-details/<int:pk>/edit/', views.FormDetailsUpdateView.as_view(), name='form-details-edit'),
    path('admin/form-details/<int:pk>/delete/', views.FormDetailsDeleteView.as_view(), name='form-details-delete'),

    # Admin: Create Tables In Form
    path('admin/form-tables/', views.FormTableInFormListView.as_view(), name='form-table-list'),
    path('admin/form-tables/<int:pk>/edit/', views.FormTableLayoutEditView.as_view(), name='form-table-edit'),

    # Admin: View Tables In Form
    path('admin/view-form-tables/', views.FormTableViewInFormListView.as_view(), name='form-table-view-list'),
    path('admin/view-form-tables/<int:pk>/', views.FormTableLayoutDetailView.as_view(), name='form-table-detail'),
    path('admin/view-form-tables/<int:pk>/delete/', views.FormTableLayoutDeleteView.as_view(), name='form-table-delete'),

    # Admin: Package Authorization
    path('admin/authorize/', views.PackageAuthorizationListView.as_view(), name='package-authorization-list'),
    path('admin/authorize/create/', views.PackageAuthorizationCreateView.as_view(), name='package-authorization-create'),
    path('admin/authorize/<int:pk>/', views.PackageAuthorizationDetailView.as_view(), name='package-authorization-detail'),
    path('admin/authorize/<int:pk>/edit/', views.PackageAuthorizationUpdateView.as_view(), name='package-authorization-edit'),
    path('admin/authorize/<int:pk>/delete/', views.PackageAuthorizationDeleteView.as_view(), name='package-authorization-delete'),
    path('admin/authorized-form/<int:pk>/toggle/', views.ToggleAuthorizedFormView.as_view(), name='toggle-authorized-form'),

    # Admin: Library & DDL
    path('library/', views.LibraryDocumentListView.as_view(), name='library-list'),
    path('admin/library/upload/', views.LibraryDocumentCreateView.as_view(), name='library-upload'),
    path('admin/library/<int:pk>/delete/', views.LibraryDocumentDeleteView.as_view(), name='library-delete'),
    path('library/<int:pk>/view/', views.LibraryViewView.as_view(), name='library-view'),
    path('library/<int:pk>/download/', views.LibraryDownloadView.as_view(), name='library-download'),
    path('admin/dropdown-lists/', views.DropdownListView.as_view(), name='dropdown-list'),
    path('admin/dropdown-lists/create/', views.DropdownListCreateView.as_view(), name='dropdown-create'),
    path('admin/dropdown-lists/<int:pk>/edit/', views.DropdownListEditView.as_view(), name='dropdown-edit'),
    path('admin/dropdown-lists/<int:pk>/delete/', views.DropdownListDeleteView.as_view(), name='dropdown-delete'),

    # Admin: View Package (backup)
    path('admin/view-package/', views.ViewPackageSearchView.as_view(), name='view-package'),

    # Projects (employees access via team authorization only)
    path('projects/', views.ProjectListView.as_view(), name='project-list'),
    path('forms/view/', views.ManagerViewFormsView.as_view(), name='manager-view-forms'),
    path('forms/view/master-record/', views.ManagerViewMasterRecordView.as_view(), name='manager-view-master-record'),
    path('forms/view/proposal/', views.ManagerViewProposalFormsView.as_view(), name='manager-view-proposal-forms'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project-create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project-edit'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project-delete'),
    path('projects/<int:project_id>/access/', views.ProjectAccessView.as_view(), name='project-access'),
    path('projects/<int:project_id>/team/add/', views.TeamMemberCreateView.as_view(), name='team-member-create'),
    path('team/<int:pk>/edit/', views.TeamMemberEditView.as_view(), name='team-member-edit'),
    path('team/<int:pk>/remove/', views.TeamMemberDeleteView.as_view(), name='team-member-remove'),

    # Form Records & Workflow
    path('projects/<int:project_id>/forms/<int:form_id>/create/', views.FormRecordCreateView.as_view(), name='form-record-create'),
    path('forms/<int:pk>/', views.FormRecordDetailView.as_view(), name='form-record-detail'),
    path('forms/<int:pk>/edit/', views.FormRecordEditView.as_view(), name='form-record-edit'),
    path('forms/<int:pk>/submit/', views.FormSubmitView.as_view(), name='form-submit'),
    path('forms/<int:pk>/review/', views.FormReviewView.as_view(), name='form-review'),
    path('forms/<int:pk>/finalize/', views.FormFinalizeView.as_view(), name='form-finalize'),

    # Public Forms
    path('public/form/<str:token>/', views.PublicFormView.as_view(), name='public-form'),

    # Notifications
    path('notifications/', views.NotificationsListView.as_view(), name='notifications-list'),
    path('notifications/<int:notification_id>/mark-read/', views.MarkNotificationReadView.as_view(), name='mark-notification-read'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark-all-notifications-read'),
    path('notifications/<int:notification_id>/delete/', views.DeleteNotificationView.as_view(), name='delete-notification'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
