import io
import base64

def sparkline_png_base64(series, width=560, height=64, color=None):
    """Return a base64 PNG sparkline for a numeric series.
    Series is normalized to first point (index) so the line sits around 0% baseline.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        if not series or len(series) < 2:
            return None

        y = np.array(series, dtype=float)
        base = y[0] if y[0] != 0 else 1.0
        yn = (y / base) - 1.0
        x = np.arange(len(yn))

        fig = plt.figure(figsize=(width/100, height/100), dpi=100)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.axhline(0, linewidth=1, color="#444444")
        if color is None:
            color = "#34d399" if yn[-1] >= 0 else "#f87171"
        ax.plot(x, yn, linewidth=2, color=color)

        ymin, ymax = float(yn.min()), float(yn.max())
        pad = max((ymax - ymin) * 0.2, 0.05)
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_xlim(0, len(yn) - 1)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None
