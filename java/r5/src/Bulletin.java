import java.net.URI;
import java.time.Instant;
import java.util.Objects;

record Bulletin(String revision, String published, String title, String status, String summary,
                String source, String url, String first_seen, String last_seen, String live_seen) {
    Bulletin {
        if (!Objects.requireNonNull(revision).matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("Revisión R5 inválida");
        }
        if (!"https".equals(URI.create(url).getScheme())) {
            throw new IllegalArgumentException("URL de la fuente inválida");
        }
        Instant.parse(first_seen);
        Instant.parse(last_seen);
        if (live_seen != null) Instant.parse(live_seen);
        for (String field : new String[] {published, title, status, summary, source}) {
            if (Objects.requireNonNull(field).isBlank()) throw new IllegalArgumentException("Boletín R5 incompleto");
        }
    }
}
