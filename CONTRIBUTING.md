# Contributing to vet-snomed-rag

프로젝트에 기여를 고려해 주셔서 감사합니다.
본 문서는 이슈 리포트, PR 제출, 코드 스타일 등 기본 가이드라인을 제공합니다.

---

## 1. 이슈 리포트

버그·제안·질문을 남기려면 GitHub Issues를 사용하세요.

- **버그 리포트**: 재현 절차·기대 결과·실제 결과·환경 정보(Python·OS·의존성 버전) 포함
- **기능 제안**: 해결하려는 문제와 제안하는 접근 방식을 함께 기술
- **질문**: SNOMED CT 라이선스·데이터 구축·아키텍처 관련 문의 환영

이슈 템플릿(`.github/ISSUE_TEMPLATE/`)에 따라 항목을 채워주시면 처리 속도가 빨라집니다.

---

## 2. Pull Request

### 진행 절차

1. 저장소를 fork한 뒤 feature branch 생성 (`feat/my-feature`, `fix/issue-123`)
2. 변경사항 커밋 (가능한 한 논리적 단위로 분할)
3. 테스트 실행 (tests/ 추가 예정)
4. Pull Request 제출 → PR 템플릿 항목 작성

### PR 체크리스트

- [ ] 한국어 또는 영어로 명확히 서술된 PR 설명
- [ ] 관련 이슈 번호 언급 (`Closes #123` 등)
- [ ] 민감 정보(API 키, 개인 이메일) 커밋 여부 재확인
- [ ] SNOMED CT 원본 데이터·파생 파일 미포함 확인
- [ ] 필요 시 README·CHANGELOG 업데이트

---

## 3. 코드 스타일

- **Python**: PEP 8 기반, type hint 권장
- **Commit message**: [Conventional Commits](https://www.conventionalcommits.org/) 형식 권고
  - `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **Docstring**: Google 스타일 권장
- **주석**: 한국어 또는 영어 모두 허용

---

## 4. SNOMED CT 라이선스 유의사항

본 저장소는 SNOMED International의 라이선스를 존중합니다.

- 원본 RF2 파일, 파생 벡터 인덱스, 개념별 MD 문서 등은 **절대 커밋 금지**
- `.gitignore`에 `data/`, `docs/snomed_graph*/` 등이 이미 설정됨
- 관련 규정: https://www.snomed.org/snomed-ct/get-snomed

---

## 5. 행동 강령

상호 존중을 바탕으로 한 건설적인 커뮤니케이션을 기대합니다.
