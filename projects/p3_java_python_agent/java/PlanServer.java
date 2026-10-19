import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;

/**
 * 项目三·Java 侧服务：生产计划查询与工单状态（教学用最小实现）。
 *
 * 技术选型：JDK 内置 com.sun.net.httpserver——零依赖，javac 直接编译，
 * 保证沙箱/内网环境可编译运行（Spring Boot 等价实现见 README"Spring Boot 对照"小节）。
 *
 * 端点契约（与 Python 侧 data/plans.json、workorders.json 的形状一致）：
 *   GET  /health                 → {"status":"UP","service":"plan-server"}
 *   GET  /plans?date=YYYY-MM-DD  → {"date","count","plans":[{plan_id,product,qty,status}]}
 *   GET  /workorders/{id}        → {workorder_id,plan_id,status,produced_qty,target_qty} | 404
 *   POST /adjustments            → Header: Idempotency-Key（必填，幂等去重）
 *                                  body: {plan_id,new_qty,reason}
 *                                  首次 201 {adjustment_id,...}；同 key 重放 200 + 同 adjustment_id + idempotent_replay=true
 *   GET|POST /slow?ms=N          → 延迟 N 毫秒后 {"ok":true,"delayed_ms":N}（超时/重试演示）
 *
 * 设计说明：
 *   - 数据内置内存（与 data/*.json 同形状）；data/ 目录是"契约的单一事实来源"，
 *     Python 侧契约测试会逐字段核对两边一致（Java 侧不引 JSON 库，故内置+对拍）；
 *   - 幂等账本用 ConcurrentHashMap 模拟生产里的"唯一索引 + 去重表"；
 *   - 业务规则（调整幅度、风险分级）故意不放在 Java 侧——治理属于 Agent 侧工具层
 *     （教材 54 章），Java 只做参数完整性与资源存在性校验。
 */
public class PlanServer {

    // ---- 内存数据（与 data/plans.json、data/workorders.json 逐字段一致） ----
    static final Map<String, List<Map<String, Object>>> PLANS = new ConcurrentHashMap<>();
    static final Map<String, Map<String, Object>> WORKORDERS = new ConcurrentHashMap<>();
    /** 幂等账本：Idempotency-Key → 首次响应（生产实现=数据库唯一索引+去重表）。 */
    static final Map<String, Map<String, Object>> ADJUST_SEEN = new ConcurrentHashMap<>();
    static final Map<String, Integer> ADJUST_COUNTER = new ConcurrentHashMap<>();

    public static void main(String[] args) throws IOException {
        seedData();
        int port = Integer.parseInt(System.getenv().getOrDefault("PLAN_PORT", "8080"));
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.setExecutor(Executors.newFixedThreadPool(8)); // 线程池：/slow 阻塞不拖垮其他端点
        server.createContext("/", PlanServer::route);
        server.start();
        System.out.println("LISTENING port=" + server.getAddress().getPort());
    }

    /** 路由器：一个 context 分发全部端点（教学从简；生产建议每端点独立 context）。 */
    static void route(HttpExchange ex) throws IOException {
        try {
            String path = ex.getRequestURI().getPath();
            String method = ex.getRequestMethod();
            if (path.equals("/health") && method.equals("GET")) {
                send(ex, 200, Map.of("status", "UP", "service", "plan-server"));
            } else if (path.equals("/plans") && method.equals("GET")) {
                handlePlans(ex);
            } else if (path.startsWith("/workorders/") && method.equals("GET")) {
                handleWorkorder(ex, path.substring("/workorders/".length()));
            } else if (path.equals("/adjustments") && method.equals("POST")) {
                handleAdjustments(ex);
            } else if (path.equals("/slow") && (method.equals("GET") || method.equals("POST"))) {
                handleSlow(ex);
            } else {
                send(ex, 404, Map.of("error", "not_found", "path", path));
            }
        } catch (Exception e) {
            send(ex, 500, Map.of("error", "internal_error", "detail", String.valueOf(e)));
        } finally {
            ex.close();
        }
    }

    // ---- GET /plans?date=YYYY-MM-DD --------------------------------------
    static void handlePlans(HttpExchange ex) throws IOException {
        Map<String, String> q = parseQuery(ex.getRequestURI().getRawQuery());
        String date = q.getOrDefault("date", "");
        if (!date.matches("\\d{4}-\\d{2}-\\d{2}")) {
            send(ex, 400, Map.of("error", "bad_date", "hint", "date 必须为 YYYY-MM-DD"));
            return;
        }
        List<Map<String, Object>> plans = PLANS.getOrDefault(date, List.of());
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("date", date);
        body.put("count", plans.size());
        body.put("plans", plans);
        send(ex, 200, body);
    }

    // ---- GET /workorders/{id} --------------------------------------------
    static void handleWorkorder(HttpExchange ex, String woId) throws IOException {
        Map<String, Object> wo = WORKORDERS.get(woId);
        if (wo == null) {
            send(ex, 404, Map.of("error", "workorder_not_found", "workorder_id", woId));
        } else {
            send(ex, 200, wo);
        }
    }

    // ---- POST /adjustments（Idempotency-Key 幂等） -------------------------
    static void handleAdjustments(HttpExchange ex) throws IOException {
        String idem = ex.getRequestHeaders().getFirst("Idempotency-Key");
        if (idem == null || idem.isBlank()) {
            send(ex, 400, Map.of("error", "missing_idempotency_key",
                    "hint", "写操作必须携带 Idempotency-Key 头（教材 56.3 幂等契约）"));
            return;
        }
        Map<String, Object> req = parseJson(readBody(ex));
        // 幂等命中：返回首次结果 + 标识（Java 侧不做业务校验，直接重放）
        Map<String, Object> first = ADJUST_SEEN.get(idem);
        if (first != null) {
            Map<String, Object> replay = new LinkedHashMap<>(first);
            replay.put("idempotent_replay", true);
            send(ex, 200, replay);
            return;
        }
        // 参数完整性校验（业务规则不在这一层，见类注释）
        String planId = str(req.get("plan_id"));
        Object qtyObj = req.get("new_qty");
        String reason = str(req.get("reason"));
        if (planId.isEmpty() || qtyObj == null || reason.isEmpty()) {
            send(ex, 422, Map.of("error", "invalid_adjustment",
                    "required", List.of("plan_id", "new_qty", "reason")));
            return;
        }
        int newQty;
        try {
            newQty = Integer.parseInt(String.valueOf(qtyObj));
        } catch (NumberFormatException e) {
            send(ex, 422, Map.of("error", "invalid_new_qty", "value", String.valueOf(qtyObj)));
            return;
        }
        if (newQty < 0) {
            send(ex, 422, Map.of("error", "negative_qty"));
            return;
        }
        boolean planExists = PLANS.values().stream()
                .flatMap(List::stream).anyMatch(p -> planId.equals(p.get("plan_id")));
        if (!planExists) {
            send(ex, 422, Map.of("error", "plan_not_found", "plan_id", planId));
            return;
        }
        int seq = ADJUST_COUNTER.merge("seq", 1, Integer::sum);
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("adjustment_id", String.format("ADJ-%04d", seq));
        resp.put("plan_id", planId);
        resp.put("new_qty", newQty);
        resp.put("reason", reason);
        resp.put("status", "已受理");
        resp.put("idempotency_key", idem);
        ADJUST_SEEN.put(idem, resp); // 先入账本再返回——崩溃窗口的幂等保证（教材 48/56）
        send(ex, 201, resp);
    }

    // ---- GET|POST /slow?ms=N ----------------------------------------------
    static void handleSlow(HttpExchange ex) throws IOException {
        Map<String, String> q = parseQuery(ex.getRequestURI().getRawQuery());
        int ms = Integer.parseInt(q.getOrDefault("ms", "0"));
        try {
            Thread.sleep(Math.min(ms, 10_000)); // 上限 10s：保护服务自身
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        send(ex, 200, Map.of("ok", true, "delayed_ms", ms));
    }

    // ---- 基础设施：响应 / 请求解析 -----------------------------------------
    static void send(HttpExchange ex, int code, Map<String, Object> payload) throws IOException {
        byte[] body = toJson(payload).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.sendResponseHeaders(code, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }

    static String readBody(HttpExchange ex) throws IOException {
        return new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    }

    static Map<String, String> parseQuery(String raw) {
        Map<String, String> out = new LinkedHashMap<>();
        if (raw == null || raw.isBlank()) {
            return out;
        }
        for (String kv : raw.split("&")) {
            int eq = kv.indexOf('=');
            if (eq > 0) {
                out.put(URLDecoder.decode(kv.substring(0, eq), StandardCharsets.UTF_8),
                        URLDecoder.decode(kv.substring(eq + 1), StandardCharsets.UTF_8));
            }
        }
        return out;
    }

    /** 极小 JSON：只序列化本服务的固定形状（教学从简，生产用 Jackson 等）。 */
    static String toJson(Map<String, Object> map) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Object> e : map.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(quote(e.getKey())).append(':').append(toJsonValue(e.getValue()));
        }
        return sb.append('}').toString();
    }

    @SuppressWarnings("unchecked")
    static String toJsonValue(Object v) {
        if (v == null) {
            return "null";
        }
        if (v instanceof Number || v instanceof Boolean) {
            return v.toString();
        }
        if (v instanceof Map<?, ?> m) {
            return toJson((Map<String, Object>) m);
        }
        if (v instanceof List<?> list) {
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(toJsonValue(list.get(i)));
            }
            return sb.append(']').toString();
        }
        return quote(v.toString());
    }

    static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    /** 极小 JSON 解析：只解析本服务请求的扁平对象（字符串/数字/布尔），教学从简。 */
    static Map<String, Object> parseJson(String raw) {
        Map<String, Object> out = new LinkedHashMap<>();
        String s = raw == null ? "" : raw.trim();
        if (!s.startsWith("{") || !s.endsWith("}")) {
            return out;
        }
        s = s.substring(1, s.length() - 1);
        int i = 0;
        while (i < s.length()) {
            int keyEnd = s.indexOf('"', i + 1);
            if (keyEnd < 0) {
                break;
            }
            String key = s.substring(i + 1, keyEnd);
            int colon = s.indexOf(':', keyEnd);
            if (colon < 0) {
                break;
            }
            int comma = nextTopLevelComma(s, colon);
            String valueToken = (comma < 0 ? s.substring(colon + 1) : s.substring(colon + 1, comma)).trim();
            out.put(key, parseValue(valueToken));
            if (comma < 0) {
                break;
            }
            i = comma + 1;
        }
        return out;
    }

    static int nextTopLevelComma(String s, int from) {
        boolean inString = false;
        for (int i = from + 1; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') {
                inString = !inString;
            } else if (c == ',' && !inString) {
                return i;
            }
        }
        return -1;
    }

    static Object parseValue(String t) {
        if (t.startsWith("\"") && t.endsWith("\"") && t.length() >= 2) {
            return t.substring(1, t.length() - 1);
        }
        if (t.equals("true")) {
            return Boolean.TRUE;
        }
        if (t.equals("false")) {
            return Boolean.FALSE;
        }
        if (t.equals("null")) {
            return null;
        }
        try {
            return Integer.parseInt(t);
        } catch (NumberFormatException e) {
            return t;
        }
    }

    static String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    // ---- 种子数据（与 data/plans.json、data/workorders.json 逐字段一致） ----
    static void seedData() {
        String today = LocalDate.of(2026, 3, 18).toString();
        List<Map<String, Object>> plans = new ArrayList<>();
        plans.add(Map.of("plan_id", "P-1001", "product", "减速器壳体", "qty", 500, "status", "正常"));
        plans.add(Map.of("plan_id", "P-1002", "product", "转向节", "qty", 1200, "status", "延期"));
        plans.add(Map.of("plan_id", "P-1003", "product", "制动盘", "qty", 800, "status", "正常"));
        PLANS.put(today, plans);
        PLANS.put(LocalDate.of(2026, 3, 19).toString(), new ArrayList<>(List.of(
                Map.of("plan_id", "P-1004", "product", "转向节", "qty", 1100, "status", "正常"))));
        WORKORDERS.put("WO-2091", new LinkedHashMap<>(Map.of(
                "workorder_id", "WO-2091", "plan_id", "P-1002", "status", "生产中",
                "produced_qty", 900, "target_qty", 1200)));
        WORKORDERS.put("WO-2092", new LinkedHashMap<>(Map.of(
                "workorder_id", "WO-2092", "plan_id", "P-1001", "status", "已完成",
                "produced_qty", 500, "target_qty", 500)));
    }
}
