프로젝트 전체의 버전 표기를 통일합니다.

## 1단계: 목표 버전 결정

- 인자가 있으면 그 값을 목표 버전으로 사용합니다. 예: `0.5.6`
- 인자가 없으면 `pyproject.toml`의 `version` 필드 값을 정본으로 읽어 목표 버전으로 사용합니다.

## 2단계: 전체 버전 표기 스캔

`dist/`, `.egg-info/`, `__pycache__`를 제외하고 버전 표기를 찾습니다.

```bash
grep -rn "0\.[0-9]\+\.[0-9]\+" . \
  --include="*.py" --include="*.toml" --include="*.md" \
  --include="*.html" --include="*.json" --include="*.yml" \
  | grep -v "dist/" | grep -v ".egg-info/" | grep -v "__pycache__"
```

Windows PowerShell에서는 동일한 의도로 `Get-ChildItem`과 `Select-String`을 사용해도 됩니다.

## 3단계: 불일치 파일 수정

목표 버전과 다른 표기를 아래 파일에서 찾아 수정합니다.

| 파일 | 패턴 |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/koreanstocks/__init__.py` | `VERSION = "X.Y.Z"` |
| `src/koreanstocks/core/config.py` | `VERSION = "X.Y.Z"` |
| `src/koreanstocks/api/app.py` | `version="X.Y.Z"` |
| `src/koreanstocks/static/dashboard.html` | `vX.Y.Z` |
| `README.md` | 배지 `version-X.Y.Z-blue`, 구조도 주석 |
| `AGENTS.md` | 헤더 `vX.Y.Z` |
| `CLAUDE.md` | 헤더 `vX.Y.Z`, 구조도 주석이 남아 있으면 함께 갱신 |
| `docs/ML_ANALYSIS.md` | 헤더 `vX.Y.Z` |
| `docs/NEWS_ANALYSIS.md` | 헤더 `vX.Y.Z` |
| `docs/TECHNICAL_ANALYSIS.md` | 헤더 `vX.Y.Z` |

`docs/` 내 표와 본문의 역사적 기록은 수정하지 않습니다. 예: `v0.2.3 기준 실험`, `v0.2.2 대비`.

## 4단계: 검증

수정 후 동일한 스캔을 다시 실행해 불일치 항목이 없는지 확인합니다.

## 5단계: commit & push

사용자가 커밋과 푸시까지 요청한 경우에만 변경 파일을 스테이징하고 아래 형식으로 커밋합니다.

```text
chore: 전체 버전 표기 vX.Y.Z으로 통일
```

그다음 push합니다.
