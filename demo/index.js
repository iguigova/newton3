// The page's live parts. demo/worker.js runs the repo's own Python on
// Pyodide, and demo/page.py answers for the engine; this file asks and draws.

const $ = id => document.getElementById(id);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};
const signed = n => `${n < 0 ? '−' : '+'}${Math.abs(n).toFixed(2)}`;

// One call into the worker: page.py's function NAME with ARGS, answered in turn.
const worker = new Worker('demo/worker.js', { type: 'module' });
const waiting = new Map();
let calls = 0;
worker.onmessage = ({ data: { id, result, error } }) => {
  const { resolve, reject } = waiting.get(id);
  waiting.delete(id);
  if (error === undefined) resolve(result); else reject(new Error(error));
};
const call = (name, ...args) => new Promise((resolve, reject) => {
  const id = ++calls;
  waiting.set(id, { resolve, reject });
  worker.postMessage({ id, name, args });
});

// The engine: a list of events, each a type and a number of days ago, and
// the tenant policy; every change asks the engine for the score again, and
// only the answer to the latest change is drawn.
const engine = policy => {
  const kinds = new Map(policy.events.map(e => [e.type, e]));
  const longest = Math.max(...policy.events.map(e => e.window));
  const config = { ...policy.config };
  let events = [];
  let latest = 0;

  const draw = async () => {
    const asked = ++latest;
    const result = await call('score', { config, events });
    if (asked !== latest) return;
    $('score').textContent = result.score;
    $('tier').textContent = result.tier;
    $('flag').textContent = result.force_last
      ? `Ranked last whatever the score: ${config.offence_override} or more offences in the override window.` : '';
    $('trace').replaceChildren(...result.impacts.map(i => el('tr', {},
      el('td', {}, i.name), el('td', { className: 'r' }, i.days.toFixed(0)), el('td', { className: 'r' }, signed(i.points)))));
    const parts = [`base ${result.base}`, ...result.impacts.map(i => signed(i.points))];
    if (result.cap_adjustment) parts.push(`${signed(result.cap_adjustment)} cap`);
    const gone = events.length - result.impacts.length;
    $('sum').textContent = `${parts.join(' ')} = ${result.raw.toFixed(2)} → ${result.score}`
      + (result.raw < result.floor ? ` (the floor is ${result.floor})` : '')
      + (gone ? `. ${gone === 1 ? 'One event is' : `${gone} events are`} past its window and adds nothing.` : '.');
  };

  const row = (event, index) => {
    const [type, days] = event;
    const select = el('select', {},
      ...[...kinds.values()].map(k => el('option', { value: k.type, selected: k.type === type }, k.name)));
    select.setAttribute('aria-label', `Event ${index + 1}`);
    select.addEventListener('change', () => { event[0] = select.value; draw(); });
    const output = el('output', {}, `${days} d`);
    const slider = el('input', { type: 'range', min: 0, max: longest, step: 1, value: days });
    slider.setAttribute('aria-label', `Event ${index + 1}, days ago`);
    slider.addEventListener('input', () => { event[1] = +slider.value; output.textContent = `${slider.value} d`; draw(); });
    const remove = el('button', { type: 'button', className: 'remove', title: 'Remove this event' }, '×');
    remove.setAttribute('aria-label', `Remove event ${index + 1}`);
    remove.addEventListener('click', () => { events.splice(index, 1); show(); });
    return el('li', {}, select, slider, output, remove);
  };

  const show = () => {
    $('events').replaceChildren(...(events.length
      ? events.map(row) : [el('li', { className: 'empty' }, 'No events: the score is the base.')]));
    draw();
  };

  const pick = (button, list) => {
    events = list.map(e => [...e]);
    for (const b of $('presets').children) b.setAttribute('aria-pressed', String(b === button));
    show();
  };
  const presets = Object.entries(policy.users);
  const fiveCarpools = Array.from({ length: 5 }, (_, i) => ['CARPOOL', i + 1]);
  $('presets').replaceChildren(...[...presets, ['five carpools, so the cap bites', fiveCarpools]].map(([name, list]) => {
    const button = el('button', { type: 'button' }, name);
    button.addEventListener('click', () => pick(button, list));
    return button;
  }));

  $('add').replaceChildren(...[...kinds.values()].map(k => {
    const button = el('button', { type: 'button' }, `+ ${k.name} (${k.weight > 0 ? '+' : '−'}${Math.abs(k.weight)}, ${k.window} d)`);
    button.addEventListener('click', () => { events.push([k.type, 0]); show(); });
    return button;
  }));

  const field = (key, label, step, optional) => {
    const input = el('input', { type: 'number', min: optional ? 1 : 0, step, value: config[key] ?? '' });
    input.addEventListener('input', () => {
      const value = input.value === '' ? null : +input.value;
      if (value === null && !optional) return;
      if (value !== null && (Number.isNaN(value) || value < +input.min)) return;
      config[key] = value;
      draw();
    });
    return el('label', {}, label, input);
  };
  $('policy').replaceChildren(
    field('base', 'Base', 1), field('reward_cap', 'Reward cap', 1), field('floor', 'Floor', 1),
    field('escalation', 'Escalation', 0.1), field('offence_override', 'Offences to rank last (blank: off)', 1, true));

  pick($('presets').children[presets.findIndex(([name]) => name === 'bob')], policy.users.bob);
};

// The commands: each runs the repo's own module, as `python -m` would.
const commands = () => {
  const buttons = [...$('commands').querySelectorAll('button')];
  const go = async button => {
    const argv = JSON.parse(button.dataset.run);
    const line = `$ python -m ${argv.join(' ')}`;
    buttons.forEach(b => { b.disabled = true; b.setAttribute('aria-pressed', String(b === button)); });
    $('out').textContent = `${line}\nRunning${argv[0] === 'pytest' ? '. The tests take a while' : ''}…`;
    try {
      $('out').textContent = `${line}\n${await call('run', argv)}`;
    } catch (e) {
      $('out').textContent = `${line}\nIt did not run: ${e.message}`;
    }
    buttons.forEach(b => { b.disabled = false; });
  };
  buttons.forEach(b => b.addEventListener('click', () => go(b)));
  return go(buttons[0]);
};

call('policy').then(policy => {
  $('status').hidden = true;
  $('engine').hidden = false;
  engine(policy);
  return commands();
}).catch(e => { $('status').textContent = `The engine did not load: ${e.message}.`; });
