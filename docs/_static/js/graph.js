// Show a standardisation graph full screen (see scripts/render_graphs.py).
// The button stays hidden where the browser cannot put an element full screen.
document$.subscribe(({ body }) => {
  for (const frame of body.querySelectorAll(".xh-graph")) {
    const button = frame.querySelector(".xh-graph-fullscreen")
    if (!button || !document.fullscreenEnabled) continue
    button.hidden = false
    button.onclick = () => {
      if (document.fullscreenElement === frame) document.exitFullscreen()
      else frame.requestFullscreen()
    }
    frame.onfullscreenchange = () => {
      button.textContent =
        document.fullscreenElement === frame ? "Exit full screen" : "Full screen"
    }
  }
})
