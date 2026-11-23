import com.google.gson.Gson;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;

public final class BulletinTool {
    private record Run(String at, String method, String outcome, String detail) {}
    private record Feed(boolean bundled, List<Bulletin> editions, Run lastRun) {}

    private static Feed load(Gson gson, int port) throws IOException, InterruptedException {
        var client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5)).build();
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/agroclima"))
                .timeout(Duration.ofSeconds(10)).GET().build();
        var response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("AgroEdge HTTP " + response.statusCode());
        Feed feed = gson.fromJson(response.body(), Feed.class);
        Objects.requireNonNull(feed.editions(), "Faltan las ediciones de R5");
        return feed;
    }

    public static void main(String[] args) throws IOException, InterruptedException {
        if (args.length != 1 && args.length != 3) {
            throw new IllegalArgumentException("Uso: BulletinTool PUERTO [--revision SHA256 | FECHA_DESDE FECHA_HASTA]");
        }
        Gson gson = new Gson();
        Feed dashboard = load(gson, Integer.parseInt(args[0]));
        BulletinIndex index = new BulletinIndex(dashboard.editions());
        List<Bulletin> result = index.latest();
        if (args.length == 3) {
            result = "--revision".equals(args[1]) ? index.revision(args[2]) :
                    index.between(LocalDate.parse(args[1]), LocalDate.parse(args[2]));
        }
        System.out.println(gson.toJson(new Feed(dashboard.bundled(), result, dashboard.lastRun())));
    }
}
