# Security Policy

## 지원 버전

| 버전 | 지원 상태 |
|------|-----------|
| 1.0.x | ✅ 보안 업데이트 지원 |

---

## 취약점 리포트

보안 취약점을 발견하셨다면 **공개 이슈로 등록하지 말고** 아래 방법으로 비공개 리포트 해주세요.

### 리포트 방법

- **GitHub Security Advisories**:
  https://github.com/ricocopapa/vet-snomed-rag/security/advisories/new
  (권장 — 비공개 상태로 유지됨)

### 포함할 정보

1. 취약점 유형 (예: SQL injection, API 키 노출, 의존성 취약점 등)
2. 영향 범위 및 심각도 추정
3. 재현 절차 (가능한 한 상세히)
4. 제안하는 완화 방안 (선택)

### 처리 절차

1. 접수 확인: 72시간 이내 회신
2. 영향 분석: 7일 이내
3. 패치 개발: 중요도에 따라 7~30일
4. 공개 시점: 리포터와 협의

---

## 알려진 보안 고려사항

### API 키 관리

- `.env` 파일은 `.gitignore`로 제외되어 커밋되지 않음
- `.env.example` 템플릿 제공
- 민감 키 포함 파일을 실수로 커밋한 경우 즉시 키 무효화 후 git-filter-repo 등으로 이력 제거 필요

### 의존성 관리

- `requirements.txt` 기반 Python 의존성
- Dependabot alerts를 통한 자동 취약점 추적 권장

### SNOMED CT 데이터

- 원본 RF2 파일 및 파생 산출물은 저장소 외부 관리
- 로컬 환경에서만 재생성·사용
