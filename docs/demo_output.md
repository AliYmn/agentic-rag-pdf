# Demo Output — Agentic RAG over PDF

- Document: `samples/samples-3.pdf`
- Generated: 2026-06-18T18:04:31+00:00
- Accuracy: **100%** (4/4)

Each case below shows the question, the verified answer, the verifier's judgment, the pages cited, and the tools the agent invoked.

## 1. Bu makalenin yazarı kimdir?

- **Probes:** text
- **Answer:** Bu makalenin yazarı Sultan Sarı'dır [p.1].
- **Result:** ✅ PASS (expected one of: Sultan Sar)
- **Verifier:** supported=True, confidence=1.00
- **Citations:** p.1
- **Tools used:** `search`

## 2. Yazar hangi üniversitede görev yapmaktadır?

- **Probes:** text
- **Answer:** Yazar Sultan Sarı, Ostim Teknik Üniversitesi'nde görev yapmaktadır [p.1].
- **Result:** ✅ PASS (expected one of: Ostim)
- **Verifier:** supported=True, confidence=0.99
- **Citations:** p.1
- **Tools used:** `search`, `search`

## 3. Makale hangi dergide yayımlanmıştır?

- **Probes:** text
- **Answer:** Makale, "Journal of Emerging Economies and Policy" dergisinde yayımlanmıştır [p.1].
- **Result:** ✅ PASS (expected one of: Emerging Economies, JOEEP)
- **Verifier:** supported=True, confidence=1.00
- **Citations:** p.1
- **Tools used:** `search`, `search`

## 4. Makaleye göre yapay zekânın bankacılıkta getirdiği kısıt ve zorluklardan biri nedir?

- **Probes:** text
- **Answer:** Makaleye göre, yapay zekânın bankacılıkta getirdiği kısıt ve zorluklardan biri "veri gizliliği ve güvenliği"dir. Yapay zekâ uygulamaları büyük veri setleri üzerinde çalıştığı için veri ihlalleri ve siber saldırı riskleri artmakta, bu durum da güçlü veri güvenliği politikaları gerektirmektedir [p.11, 12]. Ayrıca, "önyargı ve tarafsızlık" sorunları da yapay zekânın bankacılıkta karşılaştığı diğer zorluklar arasında yer almaktadır [p.12].
- **Result:** ✅ PASS (expected one of: siber risk, veri gizliliği, veri kalitesi, önyargı, personel)
- **Verifier:** supported=True, confidence=1.00
- **Citations:** p.12
- **Tools used:** `search`
