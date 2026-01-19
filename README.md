# 스쓰쓰브_Automation

## 시작하기

Confluence 테이블에서 필요한 컬럼을 추출하는 스크립트입니다. 기본값이 아닌 옵션을 사용하면 특정 컬럼만 추출하거나 완료된 행만 필터링할 수 있습니다.

## 프로그램 실행방법 (필수)

1. Python 3이 설치되어 있는지 확인합니다.
2. 아래 명령으로 스크립트를 실행합니다.
3. 실행 시 `user`, `token`을 순서대로 입력하면 됩니다. (`--user`, `--token` 옵션 또는 환경변수로 대체 가능)

```bash
python3 conf_table_read.py
```

## 실행 예시

```bash
python3 conf_table_read.py --col "반영여부" --only-done
```

```bash
python3 conf_table_read.py --page-id 123456 --user your_id --token your_token
```

### 옵션

* `--col` : 추출할 컬럼명 (기본값: `반영여부`)
* `--only-done` : 반영여부에 `완료`가 포함된 행만 출력
* `--conf-base` : Confluence base URL (기본값: `CONF_BASE` 환경변수 또는 `https://conf-stms.semes.com:18090`)
* `--conf-context` : Confluence context path (기본값: `CONF_CONTEXT` 환경변수 또는 `/wiki`)
* `--page-id` : Confluence 페이지 ID (기본값: `CONF_PAGE_ID` 환경변수)
* `--user` : Confluence 계정 (기본값: `CONF_USER` 환경변수, 미설정 시 입력 프롬프트)
* `--token` : Confluence 토큰/비밀번호 (기본값: `CONF_TOKEN` 환경변수, 미설정 시 입력 프롬프트)
