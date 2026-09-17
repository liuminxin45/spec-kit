import json
import subprocess
from pathlib import Path

import pytest

from test_spec_delivery_workflow import run_git, write_gerrit_workspace, write_closure_artifacts

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts/powershell'


def invoke(name, *args, cwd=None, ok=True):
    result = subprocess.run(['pwsh', '-NoProfile', '-File', str(SCRIPTS / name), *map(str, args), '-Json'],
                            cwd=cwd, capture_output=True, text=True, encoding='utf-8')
    if ok:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout
    return json.loads(result.stdout) if result.stdout.strip() else {}


def state_fixture(tmp_path):
    (tmp_path / '.specify').mkdir()
    feature = tmp_path / 'specs/001-test'
    feature.mkdir(parents=True)
    (tmp_path / '.specify/feature.json').write_text(json.dumps({
        'feature_directory': 'specs/001-test', 'delivery_profile': 'full-sdd'}))
    state = {'stage_statuses': {'acceptance': 'completed', 'commit': 'completed', 'validation': 'blocked'},
             'acceptance': {'status': 'pending'}, 'commit': {'status': 'pending'},
             'validations': [{'result': 'failed', 'evidence': 'retained'}]}
    (feature / 'workflow-state.json').write_text(json.dumps(state))
    for name in ['implementation-summary.md', 'validation.md']:
        (feature / name).write_text('# Evidence\n')
    return feature


def test_equivalent_paths_and_state_conflicts(tmp_path):
    feature = state_fixture(tmp_path)
    for path in [str(feature), feature.as_posix() + '/', 'specs/001-test']:
        result = invoke('inspect-workflow-closure.ps1', '-RepoRoot', tmp_path, '-FeatureDir', path)
        assert not any('another feature' in u for u in result['unknowns'])
        assert result['facts']['acceptance_status'] == 'completed'
        assert result['facts']['commit_status'] == 'completed'
        assert len(result['facts']['state_conflicts']) == 2


def test_writer_preserves_validation_and_updates_both_statuses(tmp_path):
    feature = state_fixture(tmp_path)
    invoke('update-workflow-state.ps1', '-FeatureDir', feature, '-Stage', 'commit', '-Status', 'completed', '-Evidence', 'commit-record.md')
    data = json.loads((feature / 'workflow-state.json').read_text())
    assert data['commit']['status'] == data['stage_statuses']['commit'] == 'completed'
    assert data['stage_statuses']['validation'] == 'blocked'
    assert data['validations'][0]['result'] == 'failed'
    assert data['next_stage_decision']['needs_resolution'] is True


def test_automatic_continuation_stops_for_failure_and_optional_stage(tmp_path):
    feature = state_fixture(tmp_path)
    path = feature / 'workflow-state.json'
    path.write_text(json.dumps({'stage_statuses': {}}))
    invoke('update-workflow-state.ps1', '-FeatureDir', feature, '-ContinuationMode', 'automatic', '-AuthorizationEvidence', 'User requested automatic default stages')
    result = invoke('resolve-next-stage.ps1', '-RepoRoot', tmp_path, '-FeatureDir', feature)
    assert result['auto_continue'] is True
    data = json.loads(path.read_text())
    data['stage_statuses'] = {'plan': 'pending'}
    data['plan'] = {'status': 'completed'}
    path.write_text(json.dumps(data))
    result = invoke('resolve-next-stage.ps1', '-RepoRoot', tmp_path, '-FeatureDir', feature)
    assert result['auto_continue'] is False
    assert result['facts']['state_conflicts'][0]['stage'] == 'plan'
    data.pop('plan')
    data['stage_statuses'] = {}
    path.write_text(json.dumps(data))
    invoke('update-workflow-state.ps1', '-FeatureDir', feature, '-Stage', 'validation', '-Status', 'failed', '-Evidence', 'failed process')
    result = invoke('resolve-next-stage.ps1', '-RepoRoot', tmp_path, '-FeatureDir', feature)
    assert result['auto_continue'] is False
    data = json.loads(path.read_text())
    data['stage_statuses'] = {'acceptance': 'completed', 'commit': 'requested'}
    path.write_text(json.dumps(data))
    result = invoke('resolve-next-stage.ps1', '-RepoRoot', tmp_path, '-FeatureDir', feature)
    assert result['next_stage'] == 'speckit.commit'
    assert result['auto_continue'] is False


@pytest.mark.parametrize('feature_commit', [True, False])
def test_two_worktree_sync_and_completion(tmp_path, feature_commit):
    remote, repo, isolated, writer = [tmp_path / n for n in ['remote.git', 'repo', 'isolated', 'writer']]
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    repo.mkdir()
    run_git(repo, 'init', '-b', 'main')
    run_git(repo, 'config', 'user.email', 'test@example.invalid')
    run_git(repo, 'config', 'user.name', 'Test')
    (repo / 'base.txt').write_text('base\n')
    run_git(repo, 'add', '.')
    run_git(repo, 'commit', '-m', 'base')
    run_git(repo, 'remote', 'add', 'origin', str(remote))
    run_git(repo, 'push', '-u', 'origin', 'main')
    run_git(repo, 'worktree', 'add', '-b', 'feature', str(isolated))
    if feature_commit:
        (isolated / 'feature.txt').write_text('feature\n')
        run_git(isolated, 'add', '.')
        run_git(isolated, 'commit', '-m', 'feature')
    subprocess.run(['git', 'clone', '-b', 'main', str(remote), str(writer)], check=True, capture_output=True)
    run_git(writer, 'config', 'user.email', 'test@example.invalid')
    run_git(writer, 'config', 'user.name', 'Test')
    (writer / 'remote.txt').write_text('remote\n')
    run_git(writer, 'add', '.')
    run_git(writer, 'commit', '-m', 'remote')
    run_git(writer, 'push', 'origin', 'main')
    write_gerrit_workspace(tmp_path, repo)
    write_closure_artifacts(tmp_path)
    # A dirty Spec worktree blocks sync without switching or losing changes.
    (isolated / 'base.txt').write_text('dirty\n')
    blocked = invoke('sync-spec-branches.ps1', '-RepoRoot', tmp_path, '-ConfirmSync', ok=False)
    assert blocked['status'] == 'blocked'
    assert (isolated / 'base.txt').read_text() == 'dirty\n'
    (isolated / 'base.txt').write_text('base\n')
    synced = invoke('sync-spec-branches.ps1', '-RepoRoot', tmp_path, '-ConfirmSync')
    assert Path(synced['facts']['repositories'][0]['path']) == isolated
    assert run_git(repo, 'branch', '--show-current') == 'main'
    # Completion preflight also audits the isolated worktree before mutation.
    (isolated / 'base.txt').write_text('dirty\n')
    blocked = invoke('complete-spec-branches.ps1', '-Branch', 'feature', '-PreflightOnly', cwd=tmp_path, ok=False)
    assert any('tracked changes' in e for e in blocked['errors'])
    (isolated / 'base.txt').write_text('base\n')
    completed = invoke('complete-spec-branches.ps1', '-Branch', 'feature', '-ConfirmCompletion', cwd=tmp_path)
    assert completed['action'] == 'completed'
    assert run_git(repo, 'branch', '--show-current') == 'main'
    assert run_git(isolated, 'branch', '--show-current') == ''
    assert run_git(repo, 'rev-list', '--merges', 'origin/main..main') == ''
    assert run_git(repo, 'rev-parse', 'feature')
    assert (repo / 'remote.txt').read_text() == 'remote\n'
    assert (repo / 'feature.txt').exists() == feature_commit
