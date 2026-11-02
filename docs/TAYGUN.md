# TAYGUN | İHA yazılım entegrasyonu ve uçuş simülasyonu

TAYGUN, üniversitede ekip olarak üzerinde çalıştığımız sabit kanatlı İHA projesi. Ben simülasyon ve yazılım entegrasyonu tarafında görev alıyorum. Bu sayfa, kaynak kodu özel depoda bulunan projenin kısa tanıtımıdır.

## Benim çalışma alanım

Görevim, Gazebo'daki uçak simülasyonunu PX4 ile çalıştırmak ve uçuş durumunu QGroundControl üzerinden izleyebilmek. Bu kapsamda kamera verisi, telemetri ve simülasyon bileşenlerinin birlikte çalışması üzerine çalışıyorum.

- PX4 ve Gazebo uçuş simülasyonunun kurulumu ve entegrasyonu.
- QGroundControl ile konum, uçuş durumu ve telemetri takibi.
- Sanal kameradan gelen görüntülerin Python tarafında işlenmesi ve algılama/takip denemeleri.
- Simülasyonda kalkış, eve dönüş ve belirlenen noktaya iniş senaryolarının denenmesi.

Uçak tasarımı ve özel algılama modeli ekipte ayrı çalışmalar olarak ilerliyor.

## Kullanılan araçlar

| Alan | Araçlar |
| --- | --- |
| Uçuş simülasyonu | PX4 SITL, Gazebo |
| Yer istasyonu | QGroundControl |
| Haberleşme ve veri akışı | ROS 2, MAVLink |
| Görüntü işleme | Python, OpenCV, YOLO ile denemeler |
| Çalışma ortamı | Ubuntu / WSL |

## Mevcut aşama

Simülasyon ortamında kamera, telemetri ve bileşenler arası veri akışı üzerinde çalışıldı. Önceki takip denemelerinde işaretli bir sanal hedef kullanıldı; bu sonuç, genel İHA algılama başarısı olarak değerlendirilmiyor.

Güncel çalışma, özgün uçak modelinin entegrasyonu ve temel uçuş tutma işlevlerini içeren Pilot Relief yaklaşımına odaklanıyor. Özgün uçak verileri, kontrol ayarları ve özel algılama modeliyle yapılacak doğrulamalar sürüyor. Canlı hedef yönlendirmesi mevcut sürümde kapalı. Buradaki denemeler simülasyonla sınırlı; gerçek uçuş doğrulaması ayrı bir aşama.

## Kod ve inceleme

Kaynak kod şu anda özel depoda tutuluyor. Burada projenin amacını, benim sorumluluklarımı ve güncel aşamayı paylaşıyorum. Teknik görüşmede simülasyon düzenini, entegrasyon çalışmalarını ve yapılan denemeleri anlatabilirim. Kod paylaşımı için kapsamın ayrıca belirlenmesi gerekiyor.

[Profilime dön](https://github.com/alisimsek55)
