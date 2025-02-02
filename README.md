# Günlük Kelime Öğrenme Uygulaması

Bu uygulama, kullanıcıların her gün 10 yeni İngilizce kelime öğrenmesine yardımcı olan interaktif bir web uygulamasıdır.

## Özellikler

- Her gün rastgele 10 kelime seçimi
- Her kelime için detaylı açıklama ve örnek cümleler
- Görsel destekli öğrenme
- Kelimeleri içeren interaktif hikayeler
- Günlük öğrenme özeti

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. AWS kimlik bilgilerinizi `.env` dosyasına ekleyin:
```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1
```

3. Uygulamayı çalıştırın:
```bash
python app.py
```

4. Tarayıcınızda `http://localhost:5000` adresine gidin.

## Kullanım

1. Ana sayfada günün 10 kelimesini görüntüleyin
2. "Haydi Başla" butonuna tıklayarak kelimeleri öğrenmeye başlayın
3. Her kelime için açıklamaları ve görselleri inceleyin
4. Hikaye sayfasında kelimeleri bir bağlam içinde görün
5. Günün özetinde öğrendiğiniz kelimeleri tekrar gözden geçirin

## Teknolojiler

- Flask
- AWS Bedrock (Titan Text ve Image Generation)
- Bootstrap
- Python 