import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.TreeMap;

final class BulletinIndex {
    private final Map<String, Bulletin> byRevision = new HashMap<>();
    private final NavigableMap<LocalDate, List<Bulletin>> byPublication = new TreeMap<>();

    BulletinIndex(List<Bulletin> bulletins) {
        for (Bulletin bulletin : bulletins) {
            LocalDate date = LocalDate.parse(bulletin.published());
            Bulletin previous = byRevision.putIfAbsent(bulletin.revision(), bulletin);
            if (previous == null) {
                byPublication.computeIfAbsent(date, ignored -> new ArrayList<>()).add(bulletin);
            } else if (!previous.equals(bulletin)) {
                throw new IllegalArgumentException("Hay contenido incompatible para la misma revisión");
            }
        }
    }

    List<Bulletin> between(LocalDate from, LocalDate to) {
        return byPublication.subMap(from, true, to, true).descendingMap().values().stream()
                .flatMap(List::stream).toList();
    }

    List<Bulletin> revision(String hash) {
        Bulletin bulletin = byRevision.get(hash);
        return bulletin == null ? List.of() : List.of(bulletin);
    }

    List<Bulletin> latest() {
        var latest = byPublication.lastEntry();
        return latest == null ? List.of() : List.copyOf(latest.getValue());
    }
}
