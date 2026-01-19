# 스쓰쓰브_Automation

## 시작하기

아래처럼 스크립트를 실행하세요. 실행 시 `user`, `token`을 순서대로 입력하면 됩니다.

```bash
python3 conf_table_read.py
```

### 옵션

* `--col` : 추출할 컬럼명 (기본값: `반영여부`)
* `--only-done` : 반영여부에 `완료`가 포함된 행만 출력
* `--conf-base` : Confluence base URL (기본값: `CONF_BASE` 환경변수 또는 `https://conf-stms.semes.com:18090`)
* `--conf-context` : Confluence context path (기본값: `CONF_CONTEXT` 환경변수 또는 `/wiki`)
* `--page-id` : Confluence 페이지 ID (기본값: `CONF_PAGE_ID` 환경변수)
* `--user` : Confluence 계정 (기본값: `CONF_USER` 환경변수, 미설정 시 입력 프롬프트)
* `--token` : Confluence 토큰/비밀번호 (기본값: `CONF_TOKEN` 환경변수, 미설정 시 입력 프롬프트)
