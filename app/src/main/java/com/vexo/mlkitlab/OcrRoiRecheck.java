package com.vexo.mlkitlab;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Paint;
import android.graphics.Rect;

import com.google.android.gms.tasks.Task;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognizer;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Prototipo de uma segunda leitura por regiao (ROI) para dados incertos.
 *
 * Usa a geometria original do ML Kit; NAO remove caracteres por regex,
 * NAO substitui valores de ofertas nem exporta textos, recortes ou enderecos.
 * Uma sugestao so aparece quando duas leituras do recorte concordam.
 * Essas leituras usam os mesmos pixels e nao equivalem a confirmacao humana.
 */
public final class OcrRoiRecheck {
    private OcrRoiRecheck() {}

    // Ancora espacial mesmo quando o multiplicador nao virou um numero legivel.
    private static final Pattern PRICE_ANCHOR = Pattern.compile(
        "R\\s*\\$\\s*\\d{1,4}[.,]\\d{2}", Pattern.CASE_INSENSITIVE);
    private static final Pattern RIDER_ANCHOR = Pattern.compile(
        "\\b\\d{1,5}\\s+corridas\\b",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern KM_LINE = Pattern.compile("\\bmin\\b.*\\bkm\\b",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern SURGE_LINE = Pattern.compile("\\d+[.,]\\d+\\s*[x×]",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern RATE_LINE = Pattern.compile("\\d+[.,]\\d+\\s*/\\s*km",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern KM = Pattern.compile("(?<!\\d)(\\d{1,3}(?:[.,]\\d{1,2})?)\\s*km\\b",
        Pattern.CASE_INSENSITIVE);
    private static final Pattern SURGE = Pattern.compile("(?<!\\d)([1-9][.,]\\d{1,2})\\s*[x×]\\b",
        Pattern.CASE_INSENSITIVE);
    private static final Pattern RATE = Pattern.compile("(?<![\\d.,])(\\d{1,4}[.,]\\d{2})\\s*/\\s*km\\b",
        Pattern.CASE_INSENSITIVE);

    public static final class Region {
        public final String field;
        public final Rect bounds;
        public Region(String field, Rect bounds) {
            this.field=field;
            this.bounds=new Rect(bounds);
        }
    }

    public static final class Probe {
        public final String field;
        /** Value from two separately processed variants, not trusted without human check. */
        public final String suggestion;
        public final boolean twoVariantsAgree;
        Probe(String field, String suggestion, boolean twoVariantsAgree) {
            this.field=field;
            this.suggestion=suggestion;
            this.twoVariantsAgree=twoVariantsAgree;
        }
    }

    public static List<Region> findRegions(Text scan, Bitmap image, OfferParser.Offer parsed) {
        List<Region> found=new ArrayList<>();
        if (scan==null || image==null || parsed==null) return found;
        boolean suspectTrip=parsed.get("tripKm").isEmpty() ||
                FinancialGuard.assess(parsed).reasons.stream().anyMatch(
                    reason -> reason.contains("velocidade implícita"));
        boolean suspectSurge=parsed.get("surge").isEmpty();
        boolean suspectRate=parsed.get("perKm").isEmpty();
        Rect lastTrip=null, firstLeg=null, firstSurge=null, firstRate=null;
        Rect firstPriceAnchor=null, firstRiderAnchor=null;
        // Ordem visual e coordenadas: sem depender de enderecos ou texto inteiro.
        for (Text.TextBlock block:scan.getTextBlocks()) {
            for (Text.Line line:block.getLines()) {
                Rect rect=line.getBoundingBox();
                if (rect==null) continue;
                String value=line.getText();
                if (suspectSurge && firstPriceAnchor==null &&
                    PRICE_ANCHOR.matcher(value).find() &&
                    !value.toLowerCase(Locale.ROOT).contains("aceitar por")) {
                    firstPriceAnchor=new Rect(rect);
                }
                if (suspectSurge && firstRiderAnchor==null &&
                    RIDER_ANCHOR.matcher(value).find()) firstRiderAnchor=new Rect(rect);
                if (suspectTrip && KM_LINE.matcher(value).find()) {
                    if (firstLeg==null || rect.top<firstLeg.top) firstLeg=new Rect(rect);
                    if (lastTrip==null || rect.top>lastTrip.top) lastTrip=new Rect(rect);
                }
                if (suspectSurge && firstSurge==null && SURGE_LINE.matcher(value).find()) firstSurge=rect;
                if (suspectRate && firstRate==null && RATE_LINE.matcher(value).find()) firstRate=rect;
            }
        }
        // Fallback por CONTEXTO: mesmo se o OCR nao vir "2,8x" nem o "x",
        // procurar a faixa entre preco principal e perfil de corridas.
        // Essa ROI e uma hipotese de leitura, NAO prova de que exista dinamica.
        if (suspectSurge && firstSurge==null &&
            firstPriceAnchor!=null && firstRiderAnchor!=null &&
            firstRiderAnchor.top>firstPriceAnchor.top) {
            int gap=firstRiderAnchor.top-firstPriceAnchor.bottom;
            // Recusar layouts muito afastados/ambiguos: evitar incluir GPS/mapa.
            if (gap>=12 && gap<=Math.min(330,image.getHeight()/3)) {
                int padX=Math.max(18,image.getWidth()/18);
                int left=Math.max(0,Math.min(firstPriceAnchor.left,firstRiderAnchor.left)-padX);
                int right=Math.min(image.getWidth(),Math.max(
                    Math.max(firstPriceAnchor.right,firstRiderAnchor.right)+padX,
                    Math.round(image.getWidth()*0.72f)));
                int top=Math.max(0,firstPriceAnchor.top-14);
                int bottom=Math.min(image.getHeight(),firstRiderAnchor.top+12);
                if (right>left && bottom>top)
                    firstSurge=new Rect(left,top,right,bottom);
            }
        }
        // Nunca usar a unica distancia visivel como viagem: pode ser a busca!
        // Na amostra real com sobreposicao social (0.3.5) o ROI sugeriu
        // pickupKm 1,9 / 5,7 quando tripKm 161,3 / 4,9 estava oculto.
        // Exigir duas linhas espaciais separadas. Caso contrario: abster.
        if (firstLeg!=null && lastTrip!=null &&
            lastTrip.top>=firstLeg.bottom+4) {
            found.add(new Region("tripKm",padded(lastTrip,image)));
        }
        if (firstSurge!=null) found.add(new Region("surge",
            // Fallback ja tem margem controlada; sem estender para GPS.
            padded(firstSurge,image)));
        if (firstRate!=null) found.add(new Region("perKm",padded(firstRate,image)));
        return found;
    }

    private static Rect padded(Rect r, Bitmap bitmap) {
        int horizontal=Math.max(18,Math.round(r.width()*0.24f));
        int vertical=Math.max(12,Math.round(r.height()*0.45f));
        return new Rect(Math.max(0,r.left-horizontal),Math.max(0,r.top-vertical),
            Math.min(bitmap.getWidth(),r.right+horizontal),
            Math.min(bitmap.getHeight(),r.bottom+vertical));
    }

    private static Bitmap expanded(Bitmap original, Rect rect, int requestedScale, boolean enhance) {
        int scale=Math.max(1,Math.min(requestedScale,
            Math.min(1600/Math.max(1,rect.width()),1200/Math.max(1,rect.height()))));
        Bitmap out=Bitmap.createBitmap(Math.max(1,rect.width()*scale),
            Math.max(1,rect.height()*scale),Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(out);
        Paint paint=new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
        if (enhance) {
            // Contraste moderado. Nunca altera os pixels da imagem original.
            ColorMatrix matrix=new ColorMatrix(new float[]{
                1.35f,0,0,0,-36,
                0,1.35f,0,0,-36,
                0,0,1.35f,0,-36,
                0,0,0,1,0
            });
            paint.setColorFilter(new ColorMatrixColorFilter(matrix));
        }
        canvas.drawBitmap(original,rect,new Rect(0,0,out.getWidth(),out.getHeight()),paint);
        return out;
    }

    private static String singleValue(String text, String field) {
        Pattern pattern="tripKm".equals(field)?KM:"surge".equals(field)?SURGE:RATE;
        Matcher matcher=pattern.matcher(text==null?"":text);
        String first="";
        while (matcher.find()) {
            String candidate=matcher.group(1).replace('.',',');
            if (!first.isEmpty() && !first.equals(candidate)) return "";
            first=candidate;
        }
        return first;
    }

    /**
     * Duas leituras independentes de processamento, nao da origem dos pixels.
     * Nunca alterar o OfferParser.Offer; resultado apenas para diagnostico/revisao.
     */
    public static Task<Probe> recheck(TextRecognizer recognizer, Bitmap original, Region region) {
        final Bitmap zoom=expanded(original,region.bounds,2,false);
        return recognizer.process(InputImage.fromBitmap(zoom,0)).continueWithTask(firstTask -> {
            String first=firstTask.isSuccessful()?singleValue(firstTask.getResult().getText(),region.field):"";
            zoom.recycle();
            final Bitmap enhanced=expanded(original,region.bounds,3,true);
            return recognizer.process(InputImage.fromBitmap(enhanced,0)).continueWith(secondTask -> {
                String second=secondTask.isSuccessful()?
                    singleValue(secondTask.getResult().getText(),region.field):"";
                enhanced.recycle();
                boolean agree=!first.isEmpty() && first.equals(second);
                return new Probe(region.field,agree?first:"",agree);
            });
        });
    }
}
