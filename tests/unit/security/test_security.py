"""Security layer (11): token auth, RBAC, PII redaction, audit, override."""

from __future__ import annotations

from datetime import datetime

import pytest

from aegis.domain import InsufficientPermission, Role
from aegis.domain.time import UTC
from aegis.security.audit import InMemorySecretsProvider, MemoryAuditLogger
from aegis.security.auth import HmacTokenAuthProvider
from aegis.security.models import (
    AuthContext,
    AuthMethod,
    Credentials,
    DataClassification,
    Permission,
    PIIMatch,
    PIIType,
    RedactedString,
)
from aegis.security.override import can_override_gate
from aegis.security.pii import DefaultClassificationAnnotator, RegexPIIDetector
from aegis.security.rbac import ROLE_PERMISSIONS, RBACPermissionChecker

pytestmark = pytest.mark.unit


def _context(user_id="alice", org="org:1", role=Role.OWNER) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        organization_id=org,
        project_id="prj:1",
        role=role,
        authentication_method=AuthMethod.OAUTH2,
        authenticated_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def test_token_signing_roundtrip():
    provider = HmacTokenAuthProvider("secret")
    token = provider.issue("alice", "org:1", Role.ENGINEER, project_id="prj:1")
    context = provider.validate_token(token)
    assert context.user_id == "alice"
    assert context.organization_id == "org:1"
    assert context.role is Role.ENGINEER
    assert context.project_id == "prj:1"
    assert context.token_expiry is not None


def test_token_authenticate_via_credentials():
    provider = HmacTokenAuthProvider("secret")
    token = provider.issue("bob", "org:2", Role.ANALYST)
    context = provider.authenticate(Credentials(bearer_token=token))
    assert context.user_id == "bob"


def test_token_malformed_rejected():
    provider = HmacTokenAuthProvider("secret")
    with pytest.raises(InsufficientPermission):
        provider.validate_token("not-a-token")
    with pytest.raises(InsufficientPermission):
        provider.validate_token("aegis.v1.bad.tampered")


def test_token_tampered_payload_rejected():
    provider = HmacTokenAuthProvider("secret")
    token = provider.issue("alice", "org:1", Role.OWNER)
    body, sig = token.rsplit(".", 1)
    tampered = body[:-1] + ("B" if body[-1] != "B" else "C")
    with pytest.raises(InsufficientPermission):
        provider.validate_token(f"{tampered}.{sig}")


def test_token_expired_rejected():
    from datetime import timedelta

    provider = HmacTokenAuthProvider("secret", token_ttl=timedelta(days=-1))
    token = provider.issue(
        "alice",
        "org:1",
        Role.OWNER,
        now=datetime(2026, 1, 2, tzinfo=UTC),
    )
    with pytest.raises(InsufficientPermission):
        provider.validate_token(token)


def test_rbac_owner_holds_every_permission():
    checker = RBACPermissionChecker()
    context = _context()
    checker.check(context, Permission.ORGANIZATION_MANAGE, "org:1")


def test_rbac_analyst_cannot_modify_policy():
    checker = RBACPermissionChecker()
    context = _context(role=Role.ANALYST)
    assert not checker.has_permission(context, Permission.POLICY_MODIFY, "org:1")
    with pytest.raises(InsufficientPermission):
        checker.check(context, Permission.POLICY_MODIFY, "org:1")


def test_rbac_cross_tenant_denied_even_for_owner():
    checker = RBACPermissionChecker()
    context = _context(role=Role.OWNER)
    with pytest.raises(InsufficientPermission):
        checker.check(context, Permission.EXPERIMENT_VIEW, "org:999")


def test_rbac_engineer_permissions_match_policy():
    engineer = ROLE_PERMISSIONS[Role.ENGINEER]
    assert Permission.POLICY_OVERRIDE not in engineer
    assert Permission.EXPERIMENT_CREATE in engineer
    assert Permission.DATASET_MANAGE in engineer


def test_pii_detect_and_redact_email_phone_ssn():
    detector = RegexPIIDetector()
    text = "mail a@b.com call +1 555 0100 ssn 123-45-6789"
    matches = detector.detect(text)
    types = {m.pii_type for m in matches}
    assert PIIType.EMAIL in types
    assert PIIType.PHONE in types
    assert PIIType.SSN in types
    redacted = detector.redact(text)
    assert "a@b.com" not in redacted
    assert "<REDACTED:" in redacted


def test_pii_match_is_span_aware():
    detector = RegexPIIDetector()
    text = "user alice@example.com here"
    (match,) = detector.detect(text)
    assert isinstance(match, PIIMatch)
    assert match.start == text.index("alice")
    assert match.end == text.index(" here")
    assert text[match.start : match.end] == "alice@example.com"


def test_classification_annotator():
    annotator = DefaultClassificationAnnotator()
    assert annotator.classify({}) is DataClassification.INTERNAL
    assert annotator.classify({"tenant": "acme"}) is DataClassification.CONFIDENTIAL
    assert annotator.classify({"body": "alice@example.com"}) is DataClassification.RESTRICTED
    assert annotator.classify({"classification": "regulated"}) is DataClassification.REGULATED


def test_audit_logger_is_append_only_and_redacts_pii():
    logger = MemoryAuditLogger()
    logger.record(
        actor_id="alice",
        action="run.submit",
        resource_type="run",
        organization_id="org:1",
        metadata={"note": "owner bob@example.com"},
    )
    entries = logger.query("org:1")
    assert len(entries) == 1
    assert "bob@example.com" not in entries[0].metadata["note"]
    assert "<REDACTED:" in entries[0].metadata["note"]
    assert logger.query("org:999") == []
    assert logger.query("org:1", actor_id="bob") == []


def test_audit_filter_by_actor_and_resource():
    logger = MemoryAuditLogger()
    logger.record(actor_id="alice", action="a", resource_type="run", organization_id="org:1")
    logger.record(actor_id="bob", action="b", resource_type="experiment", organization_id="org:1")
    assert len(logger.query("org:1", actor_id="alice")) == 1
    assert len(logger.query("org:1", resource_type="experiment")) == 1


def test_secrets_provider_rotation():
    provider = InMemorySecretsProvider()
    value = provider.set_secret("api-key")
    assert provider.get_secret("api-key") == value
    provider.rotate_secret("api-key")
    assert provider.get_secret("api-key") != value


def test_redacted_string_hides_value():
    secret = RedactedString("hunter2")
    assert str(secret) == "********"
    assert "hunter2" not in repr(secret)
    assert secret.reveal() == "hunter2"


def test_service_account_never_overrides_gates():
    from aegis.policy.models import GateDecision, GateSeverity, Verdict

    context = AuthContext(
        user_id="agent",
        organization_id="org:1",
        project_id=None,
        role=Role.OWNER,
        authentication_method=AuthMethod.SERVICE_ACCOUNT,
        authenticated_at=datetime(2026, 8, 30, tzinfo=UTC),
    )
    decision = GateDecision("policy_review_gate", Verdict.FAIL, "blocked", GateSeverity.HIGH)
    assert not can_override_gate(context, decision)


def test_owner_can_override_gate():
    from aegis.policy.models import GateDecision, GateSeverity, Verdict

    context = _context(role=Role.OWNER)
    decision = GateDecision("policy_review_gate", Verdict.FAIL, "blocked", GateSeverity.HIGH)
    assert can_override_gate(context, decision)


__all__ = []
