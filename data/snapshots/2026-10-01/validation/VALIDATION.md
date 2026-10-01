# Defense OSDK reference validation — v1 candidate

## 결과

- 관측한 공식 interface record: **65**
- Root navigation에 열거된 interface: **62**
- Root navigation coverage: **62 / 62**
- Root navigation 밖에서 별도 공식 페이지로 확인된 record: **3**
- 중복 SDK ID: **0**
- unresolved outgoing target: **0**
- unresolved incoming source: **0**
- unresolved inheritance parent: **0**
- 외부/공통 기반 interface 상속 참조: **2**
- outgoing 관계인데 상대편 incoming이 없는 pair: **0**
- incoming 관계인데 상대편 outgoing이 없는 pair: **0**
- 단일 pair 기준 cardinality/required 불일치: **0**

## Root navigation 밖의 공식 페이지
- Physical Assessment
- Target List
- Target List Assignment

## Defense OSDK 바깥의 상속 부모
- Defense Geotemporal Observation → Geotemporal Observation
- Defense Tracked Entity → Tracked Entity

위 두 부모는 Defense OSDK root catalog 안의 record는 아니지만 각 Defense interface 공식 페이지의 `Extended interfaces`에서 직접 확인되므로 결손으로 보지 않았다.

## 검증 결론
현재 reference 내부의 interface link target은 모두 해소되었고, outgoing/incoming pair도 구조적으로 대칭이다.
남아 있는 핵심 리스크는 링크 결손이 아니라 공개 문서의 버전 드리프트와 일부 페이지 간 표현 차이다.
