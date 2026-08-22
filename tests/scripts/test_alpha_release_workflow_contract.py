from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_alpha_release_workflow_keeps_disposable_postgres_and_required_gates():
    workflow = (ROOT / ".github/workflows/alpha-release-certification.yml").read_text(encoding="utf-8")

    assert "alpha-postgres-rehearsal" in workflow
    assert "alpha-multi-user-golden-path" in workflow
    assert "image: postgres:16" in workflow
    assert "CFF_ALPHA_DISPOSABLE_CERTIFICATION: \"1\"" in workflow
    assert "certify_alpha_postgres_rehearsal.py" in workflow
    assert "test_espn_live_scoring.py" in workflow
    assert "test_live_scoring_recalc.py" in workflow
    assert "test_weekly_outlook_refresh.py" in workflow
    assert "run_real_stack_e2e.sh" in workflow


def test_six_manager_real_stack_scenario_is_included_in_the_real_stack_suite():
    scenario = (ROOT / "web/tests/e2e/real-stack-six-manager-golden-path.spec.ts").read_text(encoding="utf-8")
    fixtures = (ROOT / "scripts/seed_ci_beta_access_fixtures.py").read_text(encoding="utf-8")

    assert "final seat" in scenario
    assert "finalSeatStatuses.filter((status) => status === 200)).toHaveLength(1)" in scenario
    assert "new Set(ownerIds).size).toBe(6)" in scenario
    assert "ci-beta-six-manager-commissioner@example.test" in fixtures


def test_alpha_postgres_rehearsal_refuses_non_disposable_environments():
    script = (ROOT / "scripts/certify_alpha_postgres_rehearsal.py").read_text(encoding="utf-8")

    assert "CFF_ALPHA_DISPOSABLE_CERTIFICATION" in script
    assert 'in {"production", "staging"}' in script
    assert "certify_migrations()" in script
    assert "run_espn_scoring_worker.py" in script
