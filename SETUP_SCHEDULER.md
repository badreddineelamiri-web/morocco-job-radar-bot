# إعداد الجدولة التلقائية (Windows Task Scheduler)

لتشغيل النظام آلياً وبشكل دوري، يمكنك استخدام Windows Task Scheduler.

## الخطوات:

### 1. فتح Task Scheduler
- اضغط على `Win + R`
- اكتب `taskschd.msc` واضغط Enter

### 2. إنشاء مهمة جديدة
- من القائمة اليمنى، اختر "Create Basic Task"
- أعطِ المهمة اسماً مثل: `MoroccoJobRadarBot`
- الوصف: `جلب ونشر وظائف المغرب آلياً`

### 3. تحديد موعد التشغيل
- اختر "Daily" (يومي) أو "Weekly" (أسبوعي)
- حدد الوقت المناسب (مثلاً كل ساعة أو مرتين يومياً)

### 4. تحديد الإجراء
- اختر "Start a program"
- Program/script: `C:\Windows\System32\cmd.exe`
- Arguments: `/c "cd /d c:\Users\Cybader\Desktop\morocco-job-radar-bot && python main.py"`
- Start in: `c:\Users\Cybader\Desktop\morocco-job-radar-bot`

### 5. إنهاء الإعداد
- راجع الإعدادات واضغط "Finish"
- يمكنك تعديل المهمة لاحقاً لتشغيلها حتى لو لم تكن مسجل الدخول

## بديل: استخدام ملف BAT

يمكنك أيضاً تشغيل `run.bat` يدوياً أو وضعه في مجلد بدء التشغيل:
- اضغط على `Win + R`
- اكتب `shell:startup`
- ضع نسخة من `run.bat` في هذا المجلد

## ملاحظات هامة:
- تأكد من أن ملف `.env` يحتوي على مفاتيح API الصحيحة
- في البداية، استخدم `DRY_RUN=true` للاختبار
- راجع ملفات السجلات للتأكد من عمل النظام
- يمكنك تعديل `main.py` لتغيير عدد الوظائف المجلبة
