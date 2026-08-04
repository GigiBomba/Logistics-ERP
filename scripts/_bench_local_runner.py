"""Internal: run main.py and output JSON timing."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OPERION_DIAGNOSTICS"] = "0"
from main import run_app
from PySide6.QtCore import QCoreApplication

start = time.perf_counter()
app, window = run_app(return_window=True)
t_ready = time.perf_counter()
for _ in range(10):
    QCoreApplication.processEvents()
    time.sleep(0.01)
t_painted = time.perf_counter()

result = {
    "app_ready_ms": round((t_ready - start) * 1000, 1),
    "first_paint_ms": round((t_painted - start) * 1000, 1),
    "total_ms": round((time.perf_counter() - start) * 1000, 1),
}
print(json.dumps(result))
window.close()
app.quit()
