from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog
from .exchange import build_export_archive, import_archive
from .forms import BugReportForm
from .models import BugReport


def _tester(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _project_version():
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _audit_snapshot(bug):
    return {
        "screen": bug.screen,
        "screen_path": bug.screen_path,
        "title": bug.title,
        "priority": bug.priority,
        "status": bug.status,
        "assigned_to": bug.assigned_to_id,
        "root_cause": bug.root_cause,
        "fixed_version": bug.fixed_version,
        "resolution_notes": bug.resolution_notes,
        "retest_notes": bug.retest_notes,
    }


@user_passes_test(_tester, login_url="/login/")
def bug_export(request):
    archive, summary = build_export_archive(BugReport.objects.all(), exported_by=request.user.username)
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    filename = f"PAINEL_MOTORISTAS_BUGS_{stamp}.zip"
    AuditLog.objects.create(
        user=request.user,
        action="BUG_NOTEBOOK_EXPORTED",
        entity="BugReport",
        entity_id="ALL",
        after={"total": summary["total"], "open": summary["open"], "filename": filename},
    )
    response = FileResponse(archive, as_attachment=True, filename=filename, content_type="application/zip")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@user_passes_test(_tester, login_url="/login/")
def bug_import(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    package = request.FILES.get("bug_notebook_zip")
    if not package:
        messages.error(request, "Selecione um arquivo ZIP exportado pelo Caderno de Bugs.")
        return redirect("bugs")
    try:
        with transaction.atomic():
            result = import_archive(package, request.user)
            AuditLog.objects.create(
                user=request.user,
                action="BUG_NOTEBOOK_IMPORTED",
                entity="BugReport",
                entity_id="BATCH",
                after={
                    "created": result["created"],
                    "updated": result["updated"],
                    "unchanged": result["unchanged"],
                    "ignored": result["ignored"],
                    "source_app_version": result["source_app_version"],
                },
            )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("bugs")
    except Exception:
        messages.error(request, "Não foi possível importar o Caderno de Bugs. O banco não foi alterado.")
        return redirect("bugs")

    messages.success(
        request,
        "Caderno importado: "
        f"{result['created']} novo(s), {result['updated']} atualizado(s), "
        f"{result['unchanged']} sem alteração e {result['ignored']} ignorado(s).",
    )
    for error in result["errors"][:5]:
        messages.warning(request, error)
    selected = result["affected_ids"][-1] if result["affected_ids"] else ""
    return redirect(f"/bugs/?selected={selected}" if selected else "/bugs/")


@user_passes_test(_tester, login_url="/login/")
def bug_list(request):
    if request.method == "POST":
        form = BugReportForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                bug = form.save(commit=False)
                bug.created_by = request.user
                bug.app_version = _project_version()
                if not bug.browser_info:
                    bug.browser_info = request.META.get("HTTP_USER_AGENT", "")[:250]
                bug.save()
                AuditLog.objects.create(
                    user=request.user,
                    action="BUG_CREATED",
                    entity="BugReport",
                    entity_id=str(bug.pk),
                    after=_audit_snapshot(bug),
                )
            messages.success(request, f"Bug #{bug.pk} registrado no Caderno de Bugs.")
            return redirect(f"/bugs/?selected={bug.pk}")
    else:
        initial = {}
        if request.GET.get("screen"):
            initial["screen"] = request.GET["screen"]
        if request.GET.get("path"):
            initial["screen_path"] = request.GET["path"][:180]
        form = BugReportForm(initial=initial)

    qs = BugReport.objects.select_related("created_by", "assigned_to")
    screen = request.GET.get("screen", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    query = request.GET.get("q", "").strip()
    if screen:
        qs = qs.filter(screen=screen)
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(current_result__icontains=query)
            | Q(expected_result__icontains=query)
            | Q(reproduction_steps__icontains=query)
        )

    selected = None
    selected_id = request.GET.get("selected")
    if selected_id:
        try:
            selected = BugReport.objects.select_related("created_by", "assigned_to").get(pk=selected_id)
        except (BugReport.DoesNotExist, ValueError):
            selected = None

    counts = BugReport.objects.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=[BugReport.Status.OPEN, BugReport.Status.ANALYSIS, BugReport.Status.FIXING, BugReport.Status.RETEST, BugReport.Status.FAILED_RETEST])),
        p0=Count("id", filter=Q(priority=BugReport.Priority.P0) & ~Q(status__in=[BugReport.Status.RESOLVED, BugReport.Status.CLOSED])),
        p1=Count("id", filter=Q(priority=BugReport.Priority.P1) & ~Q(status__in=[BugReport.Status.RESOLVED, BugReport.Status.CLOSED])),
        retest=Count("id", filter=Q(status__in=[BugReport.Status.RETEST, BugReport.Status.FAILED_RETEST])),
        resolved=Count("id", filter=Q(status__in=[BugReport.Status.RESOLVED, BugReport.Status.CLOSED])),
    )
    screen_counts = {
        row["screen"]: row["count"]
        for row in BugReport.objects.values("screen").annotate(count=Count("id"))
    }

    page_obj = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "bugs/index.html", {
        "form": form,
        "bugs": page_obj.object_list,
        "page_obj": page_obj,
        "selected_bug": selected,
        "counts": counts,
        "screen_counts": screen_counts,
        "screens": BugReport.Screen.choices,
        "statuses": BugReport.Status.choices,
        "priorities": BugReport.Priority.choices,
        "filters": {"screen": screen, "status": status, "priority": priority, "q": query},
    })


@user_passes_test(_tester, login_url="/login/")
def bug_edit(request, pk):
    bug = get_object_or_404(BugReport.objects.select_related("created_by", "assigned_to"), pk=pk)
    before = _audit_snapshot(bug)
    if request.method == "POST":
        form = BugReportForm(request.POST, request.FILES, instance=bug)
        if form.is_valid():
            with transaction.atomic():
                bug = form.save()
                AuditLog.objects.create(
                    user=request.user,
                    action="BUG_UPDATED",
                    entity="BugReport",
                    entity_id=str(bug.pk),
                    before=before,
                    after=_audit_snapshot(bug),
                )
            messages.success(request, f"Bug #{bug.pk} atualizado.")
            return redirect(f"/bugs/?selected={bug.pk}")
    else:
        form = BugReportForm(instance=bug)
    return render(request, "bugs/edit.html", {"bug": bug, "form": form})
