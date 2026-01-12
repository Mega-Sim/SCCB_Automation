# SCCB_Automation

## 시작하기

아래 예시처럼 스크립트를 실행하세요.

```bash
python3 conf_table_read.py \
  --conf-base https://conf-stms.semes.com:18090 \
  --conf-context /wiki \
  --page-id <PAGE_ID> \
  --user <USER> \
  --token <TOKEN>
```

### 옵션

* `--col` : 추출할 컬럼명 (기본값: `반영여부`)
* `--only-done` : 반영여부에 `완료`가 포함된 행만 출력
