import io
import json
import re
import tempfile
import uuid
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BugExchangeReference, BugReport

SCHEMA_VERSION = 1
MAX_IMPORT_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_FILES = 1000
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


def _safe_filename(value, fallback="arquivo"):
    value = Path(str(value or fallback)).name
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value[:140] or fallback


def _safe_zip_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    return bool(path.parts)


def _project_version():
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _serialize_bug(bug, attachment_path=""):
    exchange_ref, _ = BugExchangeReference.objects.get_or_create(bug=bug)
    return {
        "sync_id": str(exchange_ref.sync_id),
        "local_id": bug.pk,
        "screen": bug.screen,
        "screen_display": bug.get_screen_display(),
        "screen_path": bug.screen_path,
        "title": bug.title,
        "priority": bug.priority,
        "status": bug.status,
        "status_display": bug.get_status_display(),
        "description": bug.description,
        "current_result": bug.current_result,
        "expected_result": bug.expected_result,
        "reproduction_steps": bug.reproduction_steps,
        "technical_notes": bug.technical_notes,
        "root_cause": bug.root_cause,
        "fixed_version": bug.fixed_version,
        "resolution_notes": bug.resolution_notes,
        "retest_notes": bug.retest_notes,
        "app_version": bug.app_version,
        "browser_info": bug.browser_info,
        "created_by": getattr(bug.created_by, "username", None),
        "assigned_to": getattr(bug.assigned_to, "username", None),
        "created_at": bug.created_at.isoformat() if bug.created_at else None,
        "updated_at": bug.updated_at.isoformat() if bug.updated_at else None,
        "resolved_at": bug.resolved_at.isoformat() if bug.resolved_at else None,
        "attachment": {
            "path": attachment_path,
            "original_name": Path(bug.attachment.name).name if bug.attachment else "",
        } if bug.attachment else None,
    }


def _markdown_for_bug(item):
    attachment = (item.get("attachment") or {}).get("path") or "—"
    return "\n".join([
        f"## BUG-{item.get('local_id') or '?'} — {item.get('title') or 'Sem título'}",
        "",
        f"- **Sync ID:** `{item.get('sync_id', '')}`",
        f"- **Tela:** {item.get('screen_display') or item.get('screen') or '—'}",
        f"- **Caminho:** `{item.get('screen_path') or '—'}`",
        f"- **Prioridade:** {item.get('priority') or '—'}",
        f"- **Status:** {item.get('status_display') or item.get('status') or '—'}",
        f"- **Versão:** {item.get('app_version') or '—'}",
        f"- **Registrado por:** {item.get('created_by') or '—'}",
        f"- **Responsável:** {item.get('assigned_to') or '—'}",
        f"- **Criado em:** {item.get('created_at') or '—'}",
        f"- **Atualizado em:** {item.get('updated_at') or '—'}",
        "",
        "### Descrição",
        item.get("description") or "—",
        "",
        "### Resultado atual",
        item.get("current_result") or "—",
        "",
        "### Resultado esperado",
        item.get("expected_result") or "—",
        "",
        "### Passos para reproduzir",
        item.get("reproduction_steps") or "—",
        "",
        "### Notas técnicas",
        item.get("technical_notes") or "—",
        "",
        "### Causa raiz",
        item.get("root_cause") or "—",
        "",
        f"### Correção aplicada · versão {item.get('fixed_version') or '—'}",
        item.get("resolution_notes") or "—",
        "",
        "### Reteste",
        item.get("retest_notes") or "—",
        "",
        f"### Evidência\n{attachment}",
        "",
        "---",
        "",
    ])


def build_export_archive(queryset, exported_by=""):
    """Return a seeked SpooledTemporaryFile containing the exchange ZIP."""
    bugs = list(queryset.select_related("created_by", "assigned_to").order_by("id"))
    exported_at = timezone.now()
    archive = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024, mode="w+b")
    serialized = []

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        used_names = set()
        for bug in bugs:
            attachment_path = ""
            if bug.attachment:
                original = _safe_filename(Path(bug.attachment.name).name, "evidencia")
                stem = f"BUG-{bug.pk:04d}_{original}"
                attachment_path = f"prints/{stem}"
                counter = 2
                while attachment_path.lower() in used_names:
                    attachment_path = f"prints/BUG-{bug.pk:04d}_{counter}_{original}"
                    counter += 1
                used_names.add(attachment_path.lower())
                try:
                    bug.attachment.open("rb")
                    zf.writestr(attachment_path, bug.attachment.read())
                except Exception:
                    attachment_path = ""
                finally:
                    try:
                        bug.attachment.close()
                    except Exception:
                        pass
            serialized.append(_serialize_bug(bug, attachment_path))

        priorities = Counter(item["priority"] for item in serialized)
        statuses = Counter(item["status"] for item in serialized)
        screens = Counter(item["screen"] for item in serialized)
        open_statuses = {
            BugReport.Status.OPEN,
            BugReport.Status.ANALYSIS,
            BugReport.Status.FIXING,
            BugReport.Status.RETEST,
            BugReport.Status.FAILED_RETEST,
        }
        summary = {
            "schema_version": SCHEMA_VERSION,
            "product": "Painel Motoristas",
            "app_version": _project_version(),
            "exported_at": exported_at.isoformat(),
            "exported_by": exported_by,
            "total": len(serialized),
            "open": sum(1 for item in serialized if item["status"] in open_statuses),
            "resolved": sum(1 for item in serialized if item["status"] in {BugReport.Status.RESOLVED, BugReport.Status.CLOSED}),
            "by_priority": dict(sorted(priorities.items())),
            "by_status": dict(sorted(statuses.items())),
            "by_screen": dict(sorted(screens.items())),
        }
        payload = {
            "schema_version": SCHEMA_VERSION,
            "product": "Painel Motoristas",
            "app_version": _project_version(),
            "exported_at": exported_at.isoformat(),
            "exported_by": exported_by,
            "bugs": serialized,
        }

        markdown = [
            "# Caderno de Bugs — Painel Motoristas",
            "",
            f"Exportado em: **{exported_at.strftime('%d/%m/%Y %H:%M:%S')}**",
            f"Versão: **{_project_version() or '—'}**",
            f"Total de bugs: **{len(serialized)}**",
            "",
            "> Este arquivo acompanha `bugs.json`, `resumo.json` e a pasta `prints/`. Envie o ZIP completo para análise para manter as evidências vinculadas aos registros.",
            "",
            "---",
            "",
        ]
        for item in serialized:
            markdown.append(_markdown_for_bug(item))

        zf.writestr("BUGS.md", "\n".join(markdown).encode("utf-8"))
        zf.writestr("bugs.json", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        zf.writestr("resumo.json", json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"))
        zf.writestr(
            "LEIA-ME.txt",
            (
                "PAINEL MOTORISTAS - CADERNO DE BUGS\r\n\r\n"
                "Envie este ZIP inteiro para manter BUGS.md, dados estruturados e prints juntos.\r\n"
                "O arquivo também pode ser reimportado pela tela Caderno de Bugs > Importar Caderno.\r\n"
            ).encode("utf-8"),
        )
    archive.seek(0)
    return archive, summary


def _validate_archive(uploaded_file):
    if getattr(uploaded_file, "size", 0) > MAX_IMPORT_BYTES:
        raise ValueError("O pacote do Caderno de Bugs deve ter no máximo 128 MB.")
    try:
        uploaded_file.seek(0)
        zf = zipfile.ZipFile(uploaded_file, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("O arquivo enviado não é um ZIP válido do Caderno de Bugs.") from exc

    infos = zf.infolist()
    if len(infos) > MAX_ARCHIVE_FILES:
        zf.close()
        raise ValueError("O ZIP possui arquivos demais para importação segura.")
    total = 0
    for info in infos:
        if not _safe_zip_member(info.filename):
            zf.close()
            raise ValueError("O ZIP contém um caminho de arquivo inválido.")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            zf.close()
            raise ValueError("O conteúdo descompactado do ZIP excede o limite de segurança.")
    if "bugs.json" not in zf.namelist():
        zf.close()
        raise ValueError("O ZIP não contém bugs.json.")
    return zf


def _choice_values(choices):
    return {value for value, _label in choices}


def import_archive(uploaded_file, user):
    """Merge an exported bug notebook. Returns counters and affected IDs."""
    zf = _validate_archive(uploaded_file)
    try:
        try:
            payload = json.loads(zf.read("bugs.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("bugs.json está ausente, corrompido ou em formato inválido.") from exc

        if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("bugs"), list):
            raise ValueError("Versão do formato do Caderno de Bugs não suportada.")

        valid_screens = _choice_values(BugReport.Screen.choices)
        valid_priorities = _choice_values(BugReport.Priority.choices)
        valid_statuses = _choice_values(BugReport.Status.choices)

        created = updated = unchanged = ignored = 0
        affected_ids = []
        errors = []

        for index, item in enumerate(payload["bugs"], start=1):
            if not isinstance(item, dict):
                ignored += 1
                errors.append(f"Registro {index}: formato inválido.")
                continue
            try:
                sync_id = uuid.UUID(str(item.get("sync_id", "")))
            except (ValueError, TypeError, AttributeError):
                ignored += 1
                errors.append(f"Registro {index}: sync_id inválido.")
                continue

            screen = item.get("screen")
            priority = item.get("priority")
            status = item.get("status")
            title = str(item.get("title") or "").strip()
            if screen not in valid_screens or priority not in valid_priorities or status not in valid_statuses or not title:
                ignored += 1
                errors.append(f"Registro {index}: tela, prioridade, status ou título inválido.")
                continue

            exchange_ref = BugExchangeReference.objects.select_related("bug").filter(sync_id=sync_id).first()
            if exchange_ref:
                bug = exchange_ref.bug
                was_created = False
            else:
                bug = BugReport.objects.create(
                    screen=screen,
                    title=title[:180],
                    priority=priority,
                    status=status,
                    created_by=user,
                )
                BugExchangeReference.objects.create(bug=bug, sync_id=sync_id)
                was_created = True
            before = {
                "screen": bug.screen,
                "screen_path": bug.screen_path,
                "title": bug.title,
                "priority": bug.priority,
                "status": bug.status,
                "description": bug.description,
                "current_result": bug.current_result,
                "expected_result": bug.expected_result,
                "reproduction_steps": bug.reproduction_steps,
                "technical_notes": bug.technical_notes,
                "root_cause": bug.root_cause,
                "fixed_version": bug.fixed_version,
                "resolution_notes": bug.resolution_notes,
                "retest_notes": bug.retest_notes,
                "app_version": bug.app_version,
                "browser_info": bug.browser_info,
                "assigned_to_id": bug.assigned_to_id,
            }

            bug.screen = screen
            bug.screen_path = str(item.get("screen_path") or "")[:180]
            bug.title = title[:180]
            bug.priority = priority
            bug.status = status
            bug.description = str(item.get("description") or "")
            bug.current_result = str(item.get("current_result") or "")
            bug.expected_result = str(item.get("expected_result") or "")
            bug.reproduction_steps = str(item.get("reproduction_steps") or "")
            bug.technical_notes = str(item.get("technical_notes") or "")
            bug.root_cause = str(item.get("root_cause") or "")
            bug.fixed_version = str(item.get("fixed_version") or "")[:30]
            bug.resolution_notes = str(item.get("resolution_notes") or "")
            bug.retest_notes = str(item.get("retest_notes") or "")
            bug.app_version = str(item.get("app_version") or bug.app_version or _project_version())[:30]
            bug.browser_info = str(item.get("browser_info") or "")[:250]

            assigned_username = item.get("assigned_to")
            if assigned_username:
                from django.contrib.auth import get_user_model
                bug.assigned_to = get_user_model().objects.filter(username=assigned_username, is_active=True).first()
            else:
                bug.assigned_to = None

            attachment = item.get("attachment") if isinstance(item.get("attachment"), dict) else None
            attachment_member = str((attachment or {}).get("path") or "")
            if attachment_member and attachment_member in zf.namelist() and _safe_zip_member(attachment_member):
                content = zf.read(attachment_member)
                if len(content) <= 8 * 1024 * 1024:
                    original_name = _safe_filename((attachment or {}).get("original_name") or Path(attachment_member).name, "evidencia")
                    # Keep local attachment when its content/name is already the same; otherwise save the incoming evidence.
                    current_name = Path(bug.attachment.name).name if bug.attachment else ""
                    if current_name != original_name or was_created:
                        bug.attachment.save(original_name, ContentFile(content), save=False)

            after = {
                "screen": bug.screen,
                "screen_path": bug.screen_path,
                "title": bug.title,
                "priority": bug.priority,
                "status": bug.status,
                "description": bug.description,
                "current_result": bug.current_result,
                "expected_result": bug.expected_result,
                "reproduction_steps": bug.reproduction_steps,
                "technical_notes": bug.technical_notes,
                "root_cause": bug.root_cause,
                "fixed_version": bug.fixed_version,
                "resolution_notes": bug.resolution_notes,
                "retest_notes": bug.retest_notes,
                "app_version": bug.app_version,
                "browser_info": bug.browser_info,
                "assigned_to_id": bug.assigned_to_id,
            }

            changed = was_created or before != after or bool(attachment_member)
            if changed:
                bug.save()
                if was_created:
                    created += 1
                else:
                    updated += 1
            else:
                unchanged += 1
            affected_ids.append(bug.pk)

        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "ignored": ignored,
            "errors": errors[:30],
            "affected_ids": affected_ids,
            "source_app_version": str(payload.get("app_version") or ""),
        }
    finally:
        zf.close()
