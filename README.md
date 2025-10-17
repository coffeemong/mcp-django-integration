# Django-MCP Integration Project

MCP(Model Context Protocol) 서버와 Django 웹앱 연동 프로젝트

## 프로젝트 개요

이 프로젝트는 Django 웹 애플리케이션과 MCP (Model Context Protocol) 서버 간의 통합을 구현하며, VS Code 및 Claude Desktop과의 연동을 지원합니다. 포괄적인 통합 테스트를 통해 시스템의 안정성과 신뢰성을 보장합니다.

## 기능 특징

- **Django-MCP 서버 통합**: Django 모델과 MCP 프로토콜 간의 완전한 CRUD 작업 지원
- **VS Code 연동**: MCP 확장을 통한 개발 환경 통합
- **Claude Desktop 연동**: AI 어시스턴트와의 직접 통신 지원
- **실시간 데이터 동기화**: WebSocket을 통한 실시간 업데이트
- **포괄적인 테스트**: 통합, 동시성, 장애 복구 테스트 포함

## 프로젝트 구조

```
mcp-django-integration/
├── manage.py                    # Django 관리 명령
├── requirements.txt             # Python 의존성
├── pytest.ini                  # pytest 설정
├── .gitignore                  # Git 무시 파일
│
├── myproject/                   # Django 프로젝트 설정
│   ├── settings.py             # 메인 설정
│   ├── settings_test.py        # 테스트 설정
│   ├── urls.py                 # URL 라우팅
│   ├── asgi.py                 # ASGI 설정 (WebSocket 지원)
│   └── wsgi.py                 # WSGI 설정
│
├── mcp_app/                     # Django 애플리케이션
│   ├── models.py               # 데이터 모델 (User, Memo)
│   ├── views.py                # HTTP 뷰
│   ├── urls.py                 # 앱 URL 설정
│   ├── consumers.py            # WebSocket 컨슈머
│   └── routing.py              # WebSocket 라우팅
│
├── mcp_servers/                 # MCP 서버 구현
│   ├── django_server.py        # Django MCP 서버
│   └── manager.py              # MCP 서버 매니저
│
├── config/                      # 설정 파일
│   ├── vscode_mcp.json         # VS Code MCP 설정
│   └── claude_desktop.json     # Claude Desktop 설정
│
└── tests/                       # 테스트 스위트
    ├── test_integration.py     # Django-MCP 통합 테스트
    ├── test_simple_integration.py  # 간단한 통합 테스트
    ├── test_vscode_integration.py  # VS Code 연동 테스트
    ├── test_claude_integration.py  # Claude Desktop 연동 테스트
    ├── test_concurrent_access.py   # 동시 접근 테스트
    └── test_failure_recovery.py    # 장애 복구 테스트
```

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 데이터베이스 설정

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. 테스트 실행

```bash
# 모든 테스트 실행
python -m pytest

# 특정 테스트 스위트 실행
python -m pytest tests/test_simple_integration.py -v

# VS Code 통합 테스트
python -m pytest tests/test_vscode_integration.py -v

# Claude Desktop 통합 테스트
python -m pytest tests/test_claude_integration.py -v
```

## MCP 서버 사용법

### Django MCP 서버 시작

```bash
python mcp_servers/django_server.py
```

### 사용 가능한 도구

- `list_models`: Django 모델 목록 조회
- `query_model`: 모델 데이터 쿼리
- `create_model_instance`: 모델 인스턴스 생성
- `update_model_instance`: 모델 인스턴스 업데이트
- `delete_model_instance`: 모델 인스턴스 삭제

### 예시 사용법

```python
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters

# MCP 매니저 생성
manager = MCPManager()

# 서버 시작
server_params = StdioServerParameters(
    command="python",
    args=["mcp_servers/django_server.py"],
    env={"DJANGO_SETTINGS_MODULE": "myproject.settings"}
)

await manager.add_server("django-server", server_params)

# 모델 목록 조회
tools = await manager.list_tools("django-server")
result = await manager.call_tool("django-server", "list_models", {})
```

## VS Code 연동

### 설정 파일

`config/vscode_mcp.json` 파일을 VS Code의 MCP 설정 디렉터리에 복사:

**Windows**: `%APPDATA%\Code\User\mcp.json`
**macOS**: `~/Library/Application Support/Code/User/mcp.json`
**Linux**: `~/.config/Code/User/mcp.json`

```json
{
  "servers": {
    "django-mcp-server": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_servers/django_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "myproject.settings"
      }
    }
  }
}
```

## Claude Desktop 연동

### 설정 파일

`config/claude_desktop.json` 파일의 내용을 Claude Desktop 설정에 추가:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "django-server": {
      "command": "python",
      "args": ["mcp_servers/django_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "myproject.settings"
      }
    }
  }
}
```

## 테스트 구성

### 통합 테스트

- **Django-MCP 통합**: 완전한 CRUD 워크플로우 테스트
- **실시간 동기화**: WebSocket을 통한 실시간 데이터 업데이트 테스트
- **오류 처리**: 다양한 오류 시나리오에 대한 처리 검증

### VS Code 연동 테스트

- **설정 검증**: MCP 설정 파일 형식 및 스키마 검증
- **서버 시작**: 설정을 통한 서버 시작 테스트
- **도구 발견**: 사용 가능한 MCP 도구 발견 테스트

### Claude Desktop 연동 테스트

- **프로토콜 호환성**: MCP 프로토콜 통신 테스트
- **대화 시뮬레이션**: Claude와 Django 서버 간 대화 시나리오
- **동시 세션**: 다중 Claude 세션 처리 테스트

### 동시성 및 복구 테스트

- **동시 접근**: 다중 사용자 동시 요청 처리
- **장애 복구**: 서버 재시작 및 연결 복구 테스트
- **데이터 일관성**: 동시 작업 시 데이터 무결성 보장

## 개발 가이드

### 새로운 MCP 도구 추가

1. `mcp_servers/django_server.py`에서 `@server.list_tools()` 데코레이터 함수에 새 도구 정의 추가
2. `@server.call_tool()` 데코레이터 함수에 해당 도구의 핸들러 로직 추가
3. 관련 테스트 작성

### 테스트 추가

1. 적절한 테스트 파일에 새 테스트 케이스 추가
2. `pytest.mark.integration`, `pytest.mark.unit` 등의 마커 사용
3. 비동기 테스트의 경우 `pytest.mark.asyncio` 데코레이터 사용

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.

## 기여하기

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 문의

프로젝트 관련 문의사항은 이슈 탭을 통해 남겨주세요.
