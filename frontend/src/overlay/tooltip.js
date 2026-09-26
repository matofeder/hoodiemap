const GAP_PX = 12;
const EDGE_PX = 6;

// One floating info bubble per map, placed above a point and kept inside the container.
export function createTooltip(container) {
  const tip = document.createElement('div');
  tip.className = 'gm-tip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  container.appendChild(tip);

  function show({ title, color, lines }, x, y) {
    tip.replaceChildren();
    const head = document.createElement('b');
    head.textContent = title;
    if (color) tip.style.setProperty('--c', color);
    else tip.style.removeProperty('--c');
    tip.append(head);
    for (const line of lines) {
      const row = document.createElement('span');
      row.textContent = line;
      tip.append(row);
    }
    tip.hidden = false;
    const W = container.clientWidth, w = tip.offsetWidth, h = tip.offsetHeight;
    const left = Math.min(Math.max(x - w / 2, EDGE_PX), W - w - EDGE_PX);
    const top = y - h - GAP_PX >= EDGE_PX ? y - h - GAP_PX : y + GAP_PX; // flip below near the top edge
    tip.style.transform = `translate(${left.toFixed(1)}px, ${top.toFixed(1)}px)`;
  }

  function hide() {
    tip.hidden = true;
  }

  return { show, hide, dispose: () => tip.remove() };
}
