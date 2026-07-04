from django import template

register = template.Library()


@register.filter
def can_edit_form(record, user):
    return record.can_edit(user)


@register.filter
def can_review_form(record, user):
    return record.can_review(user)


@register.filter
def can_finalize_form(record, user):
    return record.can_finalize(user)


@register.filter
def can_manage_user(editor, target):
    if not editor or not target:
        return False
    return editor.can_manage_user(target)
