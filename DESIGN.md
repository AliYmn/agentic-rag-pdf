# Mimari Tasarım — Agentic Bilgi Çıkarımı Sistemi

Çok-modlu, uzun bağlamlı PDF belgeleri üzerinde soru-cevap yapan, ajan tabanlı
bir Retrieval-Augmented Generation prototipi. Bu doküman tasarım kararlarını ve
gerekçelerini açıklar; çalıştırma adımları için `README.md`'ye bakın.

## Genel Bakış

Sistem, bir insanın belge okuma pratiğini taklit eder: **önce yapıya bak → ilgili
bölümleri getir → cevabı kanıtla doğrula.** Tek-modlu klasik RAG'in aksine, ajan
metin yetersiz kaldığında (tablo, grafik, şema) sayfayı **görüntü olarak** da
inceleyebilir.

```
                                   ┌──────────────────────────────────────────┐
   PDF ─────────┐                  │             Orchestrator Agent            │
                │                  │       (gpt-4o, araç-çağırma döngüsü)       │
                ▼                  │                                            │
        ┌───────────────┐         │   her adımda bir veya daha fazla araç:     │
        │ Ön İşleme      │         │   ┌─────────┐ ┌──────────┐ ┌────────────┐ │
        │ (PyMuPDF)      │         │   │ search  │ │view_page │ │get_outline │ │
        │ • sayfa metni  │         │   └────┬────┘ └────┬─────┘ └─────┬──────┘ │
        │ • sayfa görsel │         └────────┼───────────┼─────────────┼────────┘
        │ • JSON outline │                  │           │             │
        └───────┬───────┘                   ▼           ▼             ▼
                │                   ┌──────────────┐ ┌────────┐ ┌──────────┐
                ▼                   │   Hybrid     │ │ Sayfa  │ │ Outline  │
        ┌───────────────┐          │  Retriever   │ │ → PNG  │ │  (TOC)   │
        │  Chunking      │ ───────▶ │ BM25 ⊕ Dense │ │(base64)│ │          │
        │ (sayfa ref'li) │          │   (RRF)      │ └────────┘ └──────────┘
        └───────────────┘          └──────────────┘
                                            │  ▲ OpenAI embeddings + ChromaDB
                                   taslak cevap + kanıt
                                            ▼
                                   ┌──────────────────┐    ┌──────────────────┐
   önceki Q&A  ◀────────────────── │  Verifier Agent  │    │   Memory Store    │
   (bellek ipucu) ────────────────▶│ (bağımsız çağrı, │    │  (JSONL, görevler │
                                   │  yapılandırılmış │    │   arası öğrenme)  │
                                   │  JSON kararı)    │    └──────────────────┘
                                   └────────┬─────────┘
                                            ▼
                                    doğrulanmış cevap
                                    + atıflar [p.N] + güven skoru
```

## 1. Belge Ön İşleme

**Araç: PyMuPDF (`fitz`).** Tek bağımlılıkla hem metin çıkarımı hem de sayfa
görüntüsü render etme sağladığı için seçildi (pdfplumber görsel render etmez;
Adobe PDF Extract harici servis + maliyet gerektirir).

- **Metin:** Her sayfadan `get_text("text")` ile metin çıkarılır; sayfa numarası
  (1-tabanlı) korunur — bu, atıf (`[p.3]`) ve ileride görsel inceleme için kritik.
- **Görsel:** `view_page` aracı çağrıldığında ilgili sayfa `get_pixmap(dpi=150)`
  ile PNG'ye render edilip base64 olarak modele (gpt-4o vision) gönderilir. 150
  DPI, okunabilirlik ile token maliyeti arasında denge kurar.
- **Chunking:** Paragraf-duyarlı, karakter bütçeli (varsayılan 1200) ve overlap'li
  (200). Her chunk kaynak sayfasına bağlıdır. Tokenizer gerektirmeyen bu yaklaşım
  basit ve sağlamdır; oversized paragraflar sert bölünür.

## 2. Yapısal Navigasyon

Ajanın uzun belgede "Yöntem bölümüne git" diyebilmesi için belge yapısı açık bir
ağaç olarak temsil edilir (`OutlineNode`: başlık, seviye, sayfa, alt-düğümler).

- **Birincil kaynak:** PDF'in gömülü içindekiler tablosu (`get_toc`) — doğru ve
  bedava. Düz, seviye-etiketli liste iç içe ağaca dönüştürülür.
- **Yedek:** TOC yoksa, font-boyutu sezgiseli. Gövde metninin medyan font boyutu
  hesaplanır; bunun ≥1.5× üzeri başlıklar seviye-1, ≥1.2× üzeri seviye-2 sayılır.

Ajan `get_outline` aracıyla bu yapıyı görür ve aramadan önce nereye bakacağına
karar verir.

## 3. Retrieval Stratejisi

**Hibrit retrieval = lexical (BM25) ⊕ dense (OpenAI) → Reciprocal Rank Fusion.**

- **BM25 (`bm25s`):** Tam kelime eşleşmesini yakalar — isimler, sayılar, nadir
  terimler için güçlü (örn. "RRF constant 60").
- **Dense (OpenAI `text-embedding-3-small` + ChromaDB):** Anlamsal benzerliği
  yakalar — sorunun ifadesi kaynaktan farklı olduğunda güçlü. Ajan ile aynı
  sağlayıcı (OpenAI) kullanıldığı için tek API anahtarı yeterlidir. Index oturum
  içi bellektedir (embedding'ler belgeye özgü; bayat-önbellek hatalarını önler).
- **Füzyon (RRF, k=60):** İki sıralı liste skor ölçekleri karşılaştırılmadan
  birleştirilir; `r` sıradaki belge `1/(60+r)` katkısı yapar. Skor ölçeği
  bağımsızlığı, BM25 ve cosine gibi farklı ölçekleri güvenle harmanlamayı sağlar.

**Görsel retrieval entegrasyonu:** Metin retrieval bir tabloya/şekle işaret eden
bir sayfayı getirdiğinde, ajan o sayfayı `view_page` ile görüntü olarak çeker.
Böylece metin ve görsel kanallar, ayrı bir görsel-embedding index'i karmaşıklığı
olmadan, ajanın muhakemesi üzerinden birleşir.

## 4. Ajan Mimarisi

İki **uzmanlaşmış ajan**, OpenAI SDK üzerine sıfırdan yazılmış (LangChain yok —
döngü üzerinde tam kontrol, izlenebilirlik ve maliyet için).

- **Orchestrator:** Görevi planlar ve araçları çağıran manuel ajan döngüsünü
  yürütür (`search`, `view_page`, `get_outline`). `gpt-4o` (tool-calling + vision).
  Döngü, model araç çağırmayı bıraktığında durur; sonsuz döngüye karşı iterasyon
  sınırı vardır. Gördüğü tüm kanıt, doğrulama için biriktirilir.
- **Verifier:** Taslak cevabı **bağımsız bir LLM çağrısında** denetler — soruyu,
  cevabı ve retrieval edilen kanıtı görür ama orchestrator'ın muhakemesini görmez.
  Yapılandırılmış JSON döner: `supported`, `confidence`, `issues`, `revised_answer`.

İletişim, açık bir veri akışıyla olur (paylaşılan örtük durum değil): orchestrator
→ (cevap + kanıt) → verifier → (karar + düzeltilmiş cevap). Bu, her ajanın bağlamını
izole tutar ve onaylama yanlılığını azaltır.

## 5. Doğrulama ve Güvenilirlik

Yanlış-ama-kendinden-emin cevaplara karşı katmanlı savunma:

1. **Kanıta dayandırma:** Orchestrator yalnızca araçlardan gelen kanıtı kullanması
   ve her iddiayı `[p.N]` ile atıflandırması için yönlendirilir; cevap yoksa
   "bulunamadı" demesi istenir.
2. **Bağımsız doğrulama:** Verifier her iddiayı yalnızca sağlanan kanıta karşı
   denetler (dış bilgi kullanmaz), desteklenmeyen iddiaları işaretler ve mümkünse
   kanıta dayalı düzeltilmiş bir cevap üretir.
3. **Şeffaflık:** CLI; atıfları, güven skorunu ve (`--show-trace` ile) araç-çağrı
   izini gösterir; kullanıcı cevabın nasıl üretildiğini denetleyebilir.

**Hata yönetimi:** Eksik API anahtarı (net mesaj + exit 2), bozuk/şifreli PDF
(`ValueError`), metinsiz taranmış PDF, aralık dışı sayfa ve OpenAI API hataları
açıkça yakalanır; CLI asla ham traceback dökmez.

## 6. Bellek Yönetimi

**Görevler arası öğrenme** dosya tabanlı bir JSONL deposuyla sağlanır. Her
cevaplanan soru (soru, cevap, atıf sayfaları, güven, belge, zaman damgası) eklenir.
Yeni bir soruda, token-kümesi Jaccard örtüşmesiyle en benzer önceki kayıtlar
hatırlanır ve orchestrator'a *doğrulanması gereken ipucu* olarak verilir (körü
körüne güven değil). Eşik altı (alakasız) geçmiş hiç yüzeye çıkmaz. Basit, şeffaf
ve bağımlılıksızdır; CLI çağrıları arasında bilgi taşır.

---

## Trade-off'lar ve Sınırlar

- **Oturum-içi dense index:** Belge başına embedding maliyeti her çalıştırmada
  ödenir; karşılığında çok-belgeli senaryolarda bayat önbellek riski yoktur.
  Üretimde belge-hash'iyle anahtarlanmış kalıcı bir koleksiyon eklenebilir.
- **Görsel embedding yerine ajan-yönlendirmeli görsel:** Ayrı bir multimodal vektör
  index'i (örn. ColPali) kurmak yerine, görsel inceleme ajanın kararına bırakıldı —
  daha az altyapı, ama görsel-only içerik için doğru sayfaya metin retrieval'ın
  işaret etmesine bağımlı.
- **Maliyet/gecikme:** Doğrulama ek bir model çağrısıdır; güvenilirlik artışı
  karşılığında latency/token maliyeti getirir.

## Teknik Not — En Önemli İki Tasarım Kararı

**1. Görsel retrieval'ı ajana bir araç olarak vermek (ayrı multimodal index yerine).**
Çapraz-modal soruları çözmenin iki yolu vardı: (a) sayfa görüntüleri için ayrı bir
görsel-embedding index'i (ör. ColPali tarzı) kurmak, ya da (b) modelin (gpt-4o)
zaten multimodal olmasından yararlanıp ajana "şu sayfayı görüntü olarak incele"
diyebilen bir `view_page` aracı vermek. (b)'yi seçtim: metin retrieval ilgili sayfayı bulur,
ajan tablo/şekil olduğunu fark edip o sayfayı piksel olarak okur. Bu, ek bir vektör
deposu ve embedding ardışık düzeni olmadan çapraz-modal akıl yürütmeyi sağlar;
mimariyi sade tutar ve modelin güçlü yanını kullanır. Bedeli, görsel-only içeriğe
ulaşmak için metin retrieval'ın doğru sayfaya işaret etmesine bağımlı olmasıdır.
Sınır durumu olarak, hiç metin katmanı olmayan PDF'ler (`samples/samples-2.pdf`)
chunk üretmez; bu durumda pipeline retrieval'ı atlar ve ajan yalnızca `view_page`
+ `get_outline` ile çalışır — yani sistem tamamen taranmış/görsel belgelerde de
çökmeden iş görür.

**2. Doğrulamayı bağımsız bir ikinci ajan olarak ayırmak.** Orchestrator'a "kendini
kontrol et" demek yerine, doğrulamayı ayrı bağlamlı bir LLM çağrısına taşıdım:
verifier yalnızca soruyu, cevabı ve retrieval edilen kanıtı görür — orchestrator'ın
düşünce zincirini değil. Bu izolasyon, modelin kendi muhakemesini onaylama
eğilimini (confirmation bias) kırar ve desteklenmeyen iddiaların yakalanma olasılığını
artırır. Verifier yapılandırılmış JSON (desteklenip desteklenmediği, güven,
sorunlar, düzeltilmiş cevap) döndürdüğü için sonuç hem programatik olarak
kullanılabilir hem de kullanıcıya şeffaf bir güven sinyali sunar. Bedeli ek bir
model çağrısının maliyeti ve gecikmesidir; bunu güvenilirlik için kabul edilebilir
bir takas olarak değerlendirdim.
