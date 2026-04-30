# 원격 Push 절차

- 작성일: 2026-04-30
- 대상: 첫 origin 설정 + `v0.1.0` 태그 push
- 상태: **사용자 승인 게이트** — 본 문서는 절차만. 실제 push는 사용자 명시 승인 후 실행.

## 현재 상태

- `git remote` **비어있음** (origin 미설정)
- `v0.1.0` 로컬 annotated tag 존재 (commit `8ac96f1`)
- HEAD: `c3fba70` (HANDOFF 갱신, 0.1.0 이후 polish 4건 포함)

## 사전 점검 (push 전 필수)

### 1. 런타임 파일 누설 확인 — **해소됨** (commit `051eb37`)

- `.heartbeat`는 원래 `4bafda5` (initial commit)에 포함되어 git에 추적 중이었고, `codingbot run`이 매 사이클 갱신해 `git status`를 오염시켰음.
- `051eb37`에서 `git rm --cached .heartbeat` + `.gitignore` 등록으로 추적 해제. 워킹 트리 사본은 유지.
- 본 커밋은 `v0.1.0` 태그 이후이므로 `0.1.1` 변경 후보에 포함됨 (`docs/release-notes-0.1.1.md` 참고).

### 2. 비밀/큰 바이너리 점검

```bash
git log --all --stat | grep -iE 'api[_-]?key|secret|token|\.env' || echo "ok"
git ls-files | xargs -I{} du -k "{}" 2>/dev/null | awk '$1 > 500 {print}' || echo "no large files"
```

### 3. 태그/브랜치 상태 확인

```bash
git branch -v             # 현재 master HEAD
git tag -l --format='%(refname:short) %(subject)'  # v0.1.0 존재 확인
git log v0.1.0..HEAD --oneline  # tag 이후 추가 커밋
```

## 절차

### A. 원격 저장소 생성

GitHub 기준:
1. `https://github.com/new`에서 빈 repo 생성 (README/license/.gitignore 모두 비활성 — 로컬과 충돌 방지)
2. repo 이름 후보: `CodingBot` 또는 `codingbot`
3. visibility는 사용자 결정 (public/private)

### B. origin 등록

```bash
# SSH 사용 시
git remote add origin git@github.com:<USER>/<REPO>.git

# HTTPS 사용 시
git remote add origin https://github.com/<USER>/<REPO>.git

git remote -v   # 확인
```

### C. 첫 push (사용자 승인 필요)

```bash
# 본 push는 공유 상태를 새로 만든다 — 사용자 명시 승인 게이트
git push -u origin master
git push origin v0.1.0
# 또는 한 번에:
# git push -u origin master --tags
```

### D. push 후 확인

```bash
git remote show origin
git log origin/master..HEAD --oneline   # 비어있어야 함
```

## 주의 사항

- **force push 금지** — 본 문서의 어떤 절차도 `--force` 사용 안 함. 첫 push 후에도 master/main에 force는 별도 사용자 승인 없이는 절대 금지.
- **branch 이름** — 로컬은 `master`. 원격 default를 `main`으로 만들고 싶으면 push 전에 로컬 브랜치를 rename: `git branch -m master main` 후 절차 진행.
- **annotated tag 보존** — `v0.1.0`은 annotated. `git push origin v0.1.0`이 메시지/태거 함께 푸시함.
- **GitHub Actions / CI** — repo 생성 시점에 활성화하지 말 것. 첫 push 후 `.github/workflows/`를 추후 별도 PR로 추가하는 것이 안전.

## 사용자 승인이 필요한 행동 요약

| 행동 | 승인 필요 | 사유 |
|---|---|---|
| `git remote add origin ...` | ✓ | 새 원격 등록 — URL 결정 |
| `.heartbeat` 추적 해제 커밋 | ✓ | history 추가 |
| `git push -u origin master` | ✓ | 공유 상태 변경 (최초) |
| `git push origin v0.1.0` | ✓ | 공유 태그 등록 |

본 문서는 절차만 기술. **모든 push/원격 변경은 사용자 명시 승인 후 실행한다.**
