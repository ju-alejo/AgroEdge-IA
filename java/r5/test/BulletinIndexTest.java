import java.time.LocalDate;
import java.util.List;

public final class BulletinIndexTest {
    private static Bulletin edition(char key, String date, String status) {
        String observed = "2026-11-23T22:19:16Z";
        return new Bulletin(String.valueOf(key).repeat(64), date, "CPC", status, "Texto de prueba", "NOAA CPC",
                "https://www.cpc.ncep.noaa.gov/", observed, observed, observed);
    }

    public static void main(String[] args) {
        Bulletin older = edition('a', "2026-10-08", "A");
        Bulletin recent = edition('b', "2026-11-12", "B");
        Bulletin correction = edition('c', "2026-11-12", "C");
        BulletinIndex index = new BulletinIndex(List.of(older, correction, recent, correction));
        assert index.latest().equals(List.of(correction, recent));
        assert index.between(LocalDate.parse("2026-10-08"), LocalDate.parse("2026-11-12"))
                .equals(List.of(correction, recent, older));
        assert index.revision(older.revision()).equals(List.of(older));
        assert index.revision("unknown").isEmpty();
        try {
            new BulletinIndex(List.of(older, edition('a', "2026-10-08", "D")));
            throw new AssertionError("Se esperaba conflicto de contenido");
        } catch (IllegalArgumentException expected) {
            assert expected.getMessage().contains("misma revisión");
        }
        System.out.println("Índice R5: revisiones, fechas, duplicados y conflictos comprobados.");
    }
}
