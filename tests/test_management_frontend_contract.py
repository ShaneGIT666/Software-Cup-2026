from __future__ import annotations

from pathlib import Path


APP = Path("frontend/src/App.vue")
API = Path("frontend/src/api.ts")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_api_preserves_safe_auth_503_but_hides_arbitrary_500_messages() -> None:
    api = source(API)

    assert "serverMessage: string" in api
    assert '503: "服务配置暂不可用，请检查系统状态中的配置说明。"' in api
    assert 'error.serverMessage.startsWith("认证配置无效：")' in api
    assert '500: "服务端处理失败，请稍后重试并检查服务运行日志。"' in api
    assert '401: "登录凭证无效或已过期，请在系统状态中重新配置会话 Token。"' in api
    assert '403: "当前账号没有执行此操作的权限，请联系管理员或切换授权角色。"' in api


def test_auth_status_and_session_card_follow_runtime_auth_state() -> None:
    app = source(APP)

    assert "const authStatusLabel = computed" in app
    assert 'return "演示免认证"' in app
    assert 'return "配置无效"' in app
    assert "认证：{{ authStatusLabel }}" in app
    assert "当前为本地演示免认证模式，管理接口无需填写会话 Token。" in app
    assert "ALLOW_INSECURE_AUTH_OFF=true" in app
    assert ':disabled="authTokenInputDisabled"' in app


def test_management_workspace_survives_tab_error_and_reconnects_current_tab() -> None:
    app = source(APP)

    assert '<section class="management-workspace">' in app
    assert 'v-if="!managementPageError"' not in app
    assert "providerStatusError.value" not in app[app.index("function handleManagementServiceError"):app.index("function clearManagementServiceError")]
    assert "managementReloadKey.value += 1" in app
    for key in ("knowledge", "review", "cases", "graph", "history"):
        assert f':key="`{key}-${{managementReloadKey}}`"' in app
    open_tab = app[app.index("function openManagementTab"):app.index("function useDemoSample")]
    assert 'managementServiceError.value = ""' in open_tab


def test_initial_management_load_errors_use_banner_without_duplicate_toast() -> None:
    checks = {
        "KnowledgePanel.vue": "async function loadDocuments()",
        "ReviewPanel.vue": "async function loadCases()",
        "ReviewEventsPanel.vue": "async function loadEvents()",
    }
    for filename, marker in checks.items():
        component = source(Path("frontend/src/components") / filename)
        start = component.index(marker)
        end = component.index("\n}", start)
        initial_load = component[start:end]
        assert 'emit("serviceError", message)' in initial_load
        assert "ElMessage.error(message)" not in initial_load

    app = source(APP)
    handler = app[app.index("function handleManagementServiceError"):app.index("function clearManagementServiceError")]
    assert "message === managementServiceError.value" in handler
    assert "setInterval" not in app

