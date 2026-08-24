from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_and_ci_gates_derive_the_current_alembic_head():
    required_dynamic_consumers = (
        ROOT / ".github/workflows/ci.yml",
        ROOT / ".github/workflows/alpha-release-certification.yml",
        ROOT / ".github/workflows/espn-shadow-certification.yml",
        ROOT / "scripts/run_real_stack_e2e.sh",
    )

    for path in required_dynamic_consumers:
        contents = path.read_text(encoding="utf-8")
        assert "scripts/current_alembic_head.py" in contents
        assert 'alembic_revision == "0101_injury_notification_scope"' not in contents

    alpha_release_workflow = (ROOT / ".github/workflows/alpha-release-certification.yml").read_text(encoding="utf-8")
    assert 'test "$expected_head" = "0107_account_delete"' in alpha_release_workflow
    assert "0105_auth_token_ts_defaults" not in alpha_release_workflow
