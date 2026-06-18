# YAZILIM GELİŞTİRME ÖDEVİ

## Agentic Bilgi Çıkarımı Sistemi

**Pozisyon:** Yazılım Geliştirici — Agentic Platform Ekibi
**Süre:** 1 Hafta
**Teslim:** GitHub reposu + teknik döküman (PDF veya MD)
**Değerlendirme:** Mimari tasarım (%40) + Kod kalitesi (%40) + Sunum (%20)

---

## 1. Arka Plan ve Motivasyon

Uzun ve çok-modlu belgelerden (PDF, rapor, akademik makale) otomatik bilgi çıkarımı, gerçek dünya uygulamalarında kritik bir ihtiyaçtır. Mevcut yaklaşımlar iki temel yönelimde gelişmiştir:

Birinci yönelim, **RAG (Retrieval-Augmented Generation)** tabanlı sistemlerdir. Bu sistemler belge içeriğini indeksleyerek soruya en ilgili parçaları getirir; ancak tek bir modaliteye (yalnızca metin veya yalnızca görsel) odaklanmaları, karmaşık çapraz-modal soruları yanıtlamada yetersiz kalır.

İkinci yönelim, **ajan tabanlı (agentic) framework**'tür. Bu sistemler insanın belge okuma pratiğini taklit ederek — önce yapıya bakmak, ardından ilgili bölümlere erişmek, son olarak çapraz doğrulama yapmak — çok daha esnek bir bilgi çıkarımı gerçekleştirir.

Bu ödev, her iki paradigmayı derinlemesine anlayan, üzerinde düşünülmüş tasarım kararları alabilen ve çalışan bir prototip geliştirebilen adayları tespit etmeyi hedeflemektedir.

## 2. Görev Tanımı

Aşağıdaki iki bileşenden oluşan bir sistem tasarlayınız ve prototipler şeklinde kodlayınız:

### 2.1 Mimari Tasarım Dokümanı

Çok-modlu, uzun bağlamlı belgeler üzerinde soru-cevap yapabilen bir agentic sistem mimarisi tasarlayınız. Tasarım dokümanınız aşağıdaki soruları yanıtlamalıdır:

1. **Belge ön işleme (Document Pre-processing):** Metin ve görsel içerik nasıl ayrıştırılır? Hangi araçlar/kütüphaneler kullanılır?
2. **Yapısal navigasyon:** Ajan, uzun bir belgede ilgili bölümü nasıl bulur? Belge yapısı nasıl temsil edilir?
3. **Retrieval stratejisi:** Metin tabanlı ve görsel tabanlı arama nasıl entegre edilir?
4. **Ajan mimarisi:** Kaç ajan olacak, rolleri nedir, birbirleriyle nasıl iletişim kurar?
5. **Doğrulama ve güvenilirlik:** Yanlış cevapların önüne nasıl geçilir?
6. **Bellek yönetimi:** Görevler arası öğrenme mümkün mü? Nasıl?

**Tasarım dokümanı formatı:** Markdown veya PDF, en az 2 sayfa, mimari diyagram içermesi beklenir (ASCII diyagram da kabul edilir).

### 2.2 Yazılım Geliştirme — Minimum Viable Prototype (MVP)

Tasarımınızı destekleyen çalışan bir Python prototipi geliştirin. MVP aşağıdaki gereksinimleri karşılamalıdır:

**Zorunlu Gereksinimler**

- **Belge girişi:** En az bir PDF dosyasını okuyabilen ve metni çıkarabilen kod
- **Retrieval katmanı:** Kullanıcı sorusuna göre ilgili metin parçalarını bulan basit bir retrieval mekanizması (BM25, dense retrieval veya basit embedding tabanlı)
- **Ajan döngüsü:** Belgeyle etkileşime giren en az bir ajan; araç çağırma (tool-calling) desteği
- **Doğrulama katmanı:** İlk cevabı sorgulayan/doğrulayan en az bir mekanizma
- **CLI arayüzü:** Komut satırından çalıştırılabilir, belge yolu ve soru parametre olarak alınmalı

**Bonus (Opsiyonel) Gereksinimler**

- **Görsel içerik desteği:** PDF sayfalarını görüntü olarak işleyebilme
- **Çoklu ajan:** İki veya daha fazla uzmanlaşmış ajan
- **Bellek modülü:** Önceki sorulardan öğrenme
- **Yapılandırılmış belge taslağı (outline):** XML veya JSON formatında hiyerarşik yapı çıkarımı
- **Değerlendirme kodu:** En az 3 örnek soru-cevap çiftiyle doğruluk ölçümü

## 3. Teknik Kısıtlamalar ve Beklentiler

### 3.1 Teknoloji Seçimi

Aşağıdaki tercihler değerlendirmede olumlu etki yapar; ancak zorunlu değildir:

- Python 3.10+
- **LLM entegrasyonu için:** OpenAI API, Anthropic API veya açık kaynak modeller (Ollama ile çalıştırılabilir)
- **PDF işleme için:** PyMuPDF, pdfplumber, Adobe PDF Extract
- **Retrieval için:** FAISS, ChromaDB, BM25S
- **Ajan framework'ü için:** LangChain, LlamaIndex veya sıfırdan yazılmış özel framework

> **Not:** Eğer API maliyeti endişeniz varsa, retrieval ve ajan mantığını mock LLM yanıtlarıyla da gösterebilirsiniz. Önemli olan mimari kararların gerekçelendirilmesi ve kod kalitesidir.

### 3.2 Kod Kalitesi Beklentileri

- **Modüler yapı:** Her bileşen (preprocessing, retrieval, agent, validator) ayrı modülde
- Type hints ve docstring kullanımı
- `requirements.txt` veya `pyproject.toml`
- **README:** Kurulum ve çalıştırma adımları
- En az 3 birim testi (pytest)

## 4. Teslim Edilecekler

| # | Teslimat | Açıklama |
|---|----------|----------|
| 1 | GitHub Reposu | Public veya erişim paylaşımlı private repo |
| 2 | Mimari Tasarım Dokümanı | README içinde veya ayrı bir DESIGN.md / design.pdf |
| 3 | Çalışan MVP Kodu | Yukarıdaki zorunlu gereksinimleri karşılayan Python kodu |
| 4 | Demo Çıktısı | En az 1 PDF üzerinde 3 örnek soru-cevap çıktısı (terminal logu veya notebook) |
| 5 | Kısa Teknik Not | Yaşanan en önemli 2 tasarım kararı ve gerekçesi (200-400 kelime) |

## 5. Değerlendirme Kriterleri

| Kriter | Ne Aranır? | Ağırlık |
|--------|-----------|---------|
| Mimari Tasarım | Bileşen seçimleri gerekçeli mi? Trade-off'lar tartışılmış mı? | %40 |
| Kod Kalitesi | Modülerlik, okunabilirlik, tip tanımları, testler | %25 |
| Fonksiyonel Doğruluk | MVP çalışıyor mu? Beklenen çıktıları üretiyor mu? | %20 |
| İletişim & Sunum | Teknik not ve README netliği, kararların açıklanması | %15 |

## 6. Yol Gösterici Notlar

Bu notlar ödevi kolaylaştırmak için değil, doğru yönde düşünmenize yardımcı olmak için verilmiştir:

- **Kapsam yönetimi:** Tüm bonus gereksinimleri yapmaya çalışmak yerine, seçtiğiniz bileşenleri derinlemesine ve gerekçeli biçimde yapın. Mükemmel bir tek-ajan sistemi, yarım kalmış çok-ajan sistemden değerlidir.
- **Tasarım:** Koda başlamadan önce mimari dokümanı yazdınız mı?
- Retrieval kalitesini nelere bağlıyorsunuz?
- **Hata yönetimi:** API başarısız olursa, PDF bozuksa ne olur?

## 7. Sorular

Ödevle ilgili sorularınız için mülakat koordinatörüne başvurunuz. Teknik netleştirme soruları memnuniyetle karşılanır; kısmi çözüm ipucu talepleri değerlendirmeye dahil edilmeyecektir.

Başarılar.
