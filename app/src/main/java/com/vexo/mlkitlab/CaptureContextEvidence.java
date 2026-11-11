package com.vexo.mlkitlab;

import java.util.concurrent.atomic.AtomicLong;

/**
 * Sinais agregados para diagnosticar OCR em uma sessão autorizada.
 * Guarda SOMENTE contagens: nunca texto, imagens, números, preço,
 * nomes, localização, fingerprints ou sequência temporal de quadros.
 *
 * Os sinais podem coexistir na mesma leitura: suas contagens
 * NÃO são uma partição nem taxa de acerto.
 */
public final class CaptureContextEvidence {
    private final AtomicLong reads=new AtomicLong();
    private final AtomicLong price=new AtomicLong();
    private final AtomicLong action=new AtomicLong();
    private final AtomicLong modality=new AtomicLong();
    private final AtomicLong twoDistances=new AtomicLong();
    private final AtomicLong twoMinutes=new AtomicLong();
    private final AtomicLong literal99=new AtomicLong();
    private final AtomicLong partialOffer=new AtomicLong();

    public void reset() {
        reads.set(0);
        price.set(0);
        action.set(0);
        modality.set(0);
        twoDistances.set(0);
        twoMinutes.set(0);
        literal99.set(0);
        partialOffer.set(0);
    }

    public void record(int flags) {
        reads.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_PRICE)!=0) price.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_ACTION)!=0) action.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_MODALITY)!=0) modality.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_TWO_DISTANCES)!=0) twoDistances.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_TWO_MINUTES)!=0) twoMinutes.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_LITERAL_99)!=0) literal99.incrementAndGet();
        if((flags&ScreenContextClassifier.EVIDENCE_PARTIAL_OFFER)!=0) partialOffer.incrementAndGet();
    }

    public long[] snapshot() {
        return new long[]{reads.get(),price.get(),action.get(),modality.get(),
            twoDistances.get(),twoMinutes.get(),literal99.get(),partialOffer.get()};
    }
}
