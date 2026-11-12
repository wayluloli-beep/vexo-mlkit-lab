# Build isolado Vexo Auto ROI

Este arquivo apenas dispara o pipeline APK Express existente, cujo gatilho de push inclui branches `build/apk-express-*`.

Fonte exata: `97d58a55ec277ee539e8519443e99d787192f063` do PR draft #54.

Sem merge, sem alterar código Android/OCR dos outros agentes; apenas empacotar APK experimental que instala ao lado de PR50. Nenhum teste no celular comprovado ainda, nem oferta 99 homologada. O botão Auto depende de consentimento nativo MediaProjection e âncoras reais do ML Kit; ROI filho verde segue caixa pai azul pelo tracker. HUD não inventa FPS.
