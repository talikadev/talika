(function () {
  "use strict";

  var TERMINAL_SELECTOR =
    ".highlight.talika-terminal, pre.talika-terminal, code.talika-terminal, .termy .highlight, .termy pre, .termy code";
  var READY_ATTR = "data-talika-terminal-ready";
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var START_DELAY = 520;
  var REPLAY_DELAY = 280;
  var LINE_DELAY = 360;
  var CONTINUATION_DELAY = 210;
  var OUTPUT_DELAY = 170;
  var TYPE_DELAY = 62;
  var DEFAULT_SPEED = 2;
  var DEBUG_KEY = "talikaTerminalDebug";

  function initTalikaTerminals() {
    var targets = document.querySelectorAll(TERMINAL_SELECTOR);

    targets.forEach(enhanceTerminal);

    debug("init", {
      targets: targets.length,
      enhanced: document.querySelectorAll(".talika-terminal--enhanced").length,
      reducedMotion: reducedMotion.matches
    });
  }

  function enhanceTerminal(target) {
    var highlight = resolveTerminalContainer(target);

    if (!highlight || highlight.getAttribute(READY_ATTR) === "true") {
      return;
    }

    var code = highlight.querySelector("pre code") || highlight.querySelector("code");
    var pre = highlight.querySelector("pre") || (target.tagName === "PRE" ? target : null);
    var source = code || pre || target;
    var raw = source.textContent || "";

    if (!raw.trim()) {
      return;
    }

    var lines = parseTerminal(raw);
    var commandsToCopy = lines
      .filter(function (line) {
        return line.kind === "command";
      })
      .map(function (line) {
        return line.text;
      })
      .join("\n");

    highlight.setAttribute(READY_ATTR, "true");
    highlight.classList.add("talika-terminal", "talika-terminal--enhanced");

    if (pre) {
      pre.classList.add("talika-terminal__source");
    }

    var player = buildPlayer(highlight, lines, commandsToCopy);
    highlight.__talikaTerminalPlayer = player;
    player.highlight = highlight;
    highlight.appendChild(player.root);

    debug("enhanced", {
      title: readTerminalTitle(highlight),
      speed: player.state.speed,
      lines: lines.length,
      commands: lines.filter(function (line) {
        return line.kind === "command";
      }).length
    });

    revealWhenVisible(player);
  }

  function resolveTerminalContainer(target) {
    var highlight = target.classList.contains("highlight") ? target : target.closest(".highlight");
    var pre;
    var wrapper;

    if (highlight) {
      return highlight;
    }

    pre = target.tagName === "PRE" ? target : target.closest("pre");

    if (!pre || !pre.parentNode) {
      return null;
    }

    wrapper = document.createElement("div");
    wrapper.className = "highlight talika-terminal";
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    return wrapper;
  }

  function parseTerminal(raw) {
    var rawLines = raw.replace(/\s+$/g, "").replace(/^\s*\n/, "").split(/\r?\n/);
    var parsed = [];
    var outputBuffer = [];

    function flushOutput() {
      if (!outputBuffer.length) {
        return;
      }

      parsed.push({
        kind: "output",
        prompt: "",
        text: outputBuffer.join("\n")
      });

      outputBuffer = [];
    }

    rawLines.forEach(function (rawLine) {
      var line = rawLine.replace(/\s+$/g, "");
      var previous = parsed.length ? parsed[parsed.length - 1] : null;
      var command = parseCommandLine(line, previous);

      if (command) {
        flushOutput();
        parsed.push(command);
        return;
      }

      outputBuffer.push(line);
    });

    flushOutput();

    return parsed;
  }

  function parseCommandLine(line, previous) {
    var match;

    if (!line.trim()) {
      return null;
    }

    match = line.match(/^\s*(\$|#|>>)\s(.*)$/);
    if (match) {
      return {
        kind: "command",
        prompt: match[1],
        text: match[2],
        root: match[1] === "#"
      };
    }

    if (
      previous &&
      previous.kind === "command" &&
      previous.text.endsWith("\\") &&
      /^\s+\S/.test(line)
    ) {
      return {
        kind: "command",
        prompt: ">",
        text: line.trimStart(),
        continuation: true,
        root: false
      };
    }

    match = line.match(/^\s*([\w.-]+(?:@[\w.-]+)?(?::[~\w./-]+)?[#$])\s+(.*)$/);
    if (match) {
      return {
        kind: "command",
        prompt: match[1],
        text: match[2],
        root: match[1].endsWith("#")
      };
    }

    return null;
  }

  function buildPlayer(highlight, lines, commandsToCopy) {
    var root = document.createElement("div");
    var chrome = document.createElement("div");
    var lights = document.createElement("div");
    var title = document.createElement("div");
    var actions = document.createElement("div");
    var replay = document.createElement("button");
    var copy = document.createElement("button");
    var screen = document.createElement("div");
    var speed = readTerminalSpeed(highlight);
    var state = {
      lastMode: "idle",
      playId: 0,
      playing: false,
      speed: speed,
      started: false
    };

    state.timings = createSpeedTimings(speed);
    root.className = "talika-terminal__player";
    chrome.className = "talika-terminal__chrome";
    lights.className = "talika-terminal__lights";
    title.className = "talika-terminal__title";
    actions.className = "talika-terminal__actions";
    replay.className = "talika-terminal__button";
    copy.className = "talika-terminal__button";
    screen.className = "talika-terminal__screen";
    state.root = root;

    root.setAttribute("role", "group");
    root.setAttribute("aria-label", "Terminal example");
    root.dataset.talikaTerminalMotion = reducedMotion.matches ? "reduced-preference" : "normal";
    root.dataset.talikaTerminalSpeed = String(speed);
    root.dataset.talikaTerminalState = "ready";
    screen.setAttribute("aria-live", "off");

    title.textContent = readTerminalTitle(highlight);
    replay.type = "button";
    replay.textContent = "Replay";
    replay.setAttribute("aria-label", "Replay terminal animation");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", "Copy commands without prompts");

    for (var index = 0; index < 3; index += 1) {
      var light = document.createElement("span");
      light.className = "talika-terminal__light";
      lights.appendChild(light);
    }

    lines.forEach(function (line) {
      var row = document.createElement("div");
      var prompt = document.createElement("span");
      var code = document.createElement("span");

      row.className = "talika-terminal__line talika-terminal__line--" + line.kind;

      if (line.root) {
        row.classList.add("talika-terminal__line--root");
      }

      prompt.className = "talika-terminal__prompt";
      code.className = "talika-terminal__code";
      prompt.textContent = line.prompt;

      row.dataset.visible = "false";
      row.appendChild(prompt);
      row.appendChild(code);
      screen.appendChild(row);

      line.row = row;
      line.code = code;
    });

    replay.addEventListener("click", function () {
      play(lines, state, replay, true);
    });

    copy.addEventListener("click", function () {
      copyCommands(commandsToCopy, copy);
    });

    actions.appendChild(copy);
    actions.appendChild(replay);
    chrome.appendChild(lights);
    chrome.appendChild(title);
    chrome.appendChild(actions);
    root.appendChild(chrome);
    root.appendChild(screen);

    return {
      root: root,
      lines: lines,
      replay: replay,
      state: state
    };
  }

  function readTerminalTitle(highlight) {
    var filename = highlight.querySelector(".filename");
    var title =
      highlight.getAttribute("data-title") ||
      highlight.getAttribute("title") ||
      (filename ? filename.textContent : "");

    return title.trim() || "Terminal";
  }

  async function play(lines, state, replay, fromReplay) {
    var playId = state.playId + 1;
    state.playId = playId;
    state.lastMode = fromReplay ? "replay" : "autoplay";
    state.playing = true;
    state.started = true;
    replay.disabled = true;

    if (state.root) {
      state.root.dataset.talikaTerminalState = "playing";
    }

    resetLines(lines);

    await wait(fromReplay ? REPLAY_DELAY : START_DELAY);

    try {
      for (var lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
        var line = lines[lineIndex];

        if (state.playId !== playId) {
          return;
        }

        line.row.dataset.visible = "true";

        if (line.kind === "command") {
          await typeText(line, state, playId);
          await wait(line.continuation ? state.timings.continuationDelay : state.timings.lineDelay);
        } else {
          line.code.textContent = line.text;
          await wait(line.kind === "blank" ? state.timings.outputDelay / 2 : state.timings.outputDelay);
        }
      }
    } finally {
      if (state.playId === playId) {
        state.lastMode = "done";
        state.playing = false;
        if (state.root) {
          state.root.dataset.talikaTerminalState = "done";
        }
        replay.disabled = false;
      }
    }
  }

  async function typeText(line, state, playId) {
    line.code.textContent = "";
    line.row.classList.add("is-typing");

    await wait(80);

    for (var index = 0; index < line.text.length; index += 1) {
      if (state.playId !== playId) {
        line.row.classList.remove("is-typing");
        return;
      }

      line.code.textContent += line.text.charAt(index);
      await wait(state.timings.typeDelay + Math.min(index % 4, 2) * state.timings.typeJitter);
    }

    line.code.textContent = line.text;
    line.row.classList.remove("is-typing");
  }

  function resetLines(lines) {
    lines.forEach(function (line) {
      line.row.dataset.visible = "false";
      line.row.classList.remove("is-typing");
      line.code.textContent = "";
    });
  }

  function revealWhenVisible(player) {
    if (!("IntersectionObserver" in window)) {
      window.setTimeout(function () {
        debug("play-no-intersection-observer", diagnosePlayer(player));
        play(player.lines, player.state, player.replay, false);
      }, 140);
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !player.state.started) {
            observer.unobserve(entry.target);
            window.setTimeout(function () {
              debug("play-intersection", diagnosePlayer(player));
              play(player.lines, player.state, player.replay, false);
            }, 120);
          }
        });
      },
      { threshold: 0.22 }
    );

    observer.observe(player.root);

    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        if (!player.state.started && isInViewport(player.root)) {
          observer.unobserve(player.root);
          debug("play-viewport-fallback", diagnosePlayer(player));
          play(player.lines, player.state, player.replay, false);
        }
      });
    });
  }

  function isInViewport(node) {
    var rect = node.getBoundingClientRect();
    var height = window.innerHeight || document.documentElement.clientHeight;

    return rect.bottom > 0 && rect.top < height;
  }

  function copyCommands(commands, button) {
    if (!commands.trim()) {
      return;
    }

    writeClipboard(commands).then(function () {
      var original = button.textContent;
      button.textContent = "Copied";

      window.setTimeout(function () {
        button.textContent = original;
      }, 1200);
    });
  }

  function writeClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return writeClipboardFallback(text);
      });
    }

    return writeClipboardFallback(text);
  }

  function writeClipboardFallback(text) {
    return new Promise(function (resolve) {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      resolve();
    });
  }

  function wait(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function readTerminalSpeed(highlight) {
    var code = highlight ? highlight.querySelector("pre code") || highlight.querySelector("code") : null;
    var pre = highlight ? highlight.querySelector("pre") : null;
    var termy = highlight && highlight.closest ? highlight.closest(".termy") : null;
    var raw =
      readClassSpeed(highlight) ||
      readClassSpeed(pre) ||
      readClassSpeed(code) ||
      readClassSpeed(termy);

    var speed = Number.parseInt(raw, 10);

    if (!Number.isFinite(speed)) {
      return DEFAULT_SPEED;
    }

    return Math.max(1, Math.min(3, speed));
  }

  function readClassSpeed(node) {
    var match = node && node.className ? String(node.className).match(/(?:^|\s)speed-(\d+)(?:\s|$)/) : null;

    return match ? match[1] : "";
  }

  function createSpeedTimings(speed) {
    var timings = {
      1: {
        lineDelay: 560,
        outputDelay: 260,
        typeDelay: 118,
        typeJitter: 18
      },
      2: {
        lineDelay: LINE_DELAY,
        outputDelay: OUTPUT_DELAY,
        typeDelay: TYPE_DELAY,
        typeJitter: 11
      },
      3: {
        lineDelay: 170,
        outputDelay: 90,
        typeDelay: 24,
        typeJitter: 4
      }
    }[Math.max(1, Math.min(3, speed))];

    return {
      continuationDelay: Math.round(timings.lineDelay * 0.58),
      lineDelay: timings.lineDelay,
      outputDelay: timings.outputDelay,
      typeDelay: timings.typeDelay,
      typeJitter: timings.typeJitter
    };
  }

  function diagnosePlayer(player, index) {
    return {
      index: index,
      title: player && player.highlight ? readTerminalTitle(player.highlight) : "",
      speed: player ? player.state.speed : DEFAULT_SPEED,
      lines: player ? player.lines.length : 0,
      commands: player
        ? player.lines.filter(function (line) {
            return line.kind === "command";
          }).length
        : 0,
      started: player ? player.state.started : false,
      playing: player ? player.state.playing : false,
      mode: player ? player.state.lastMode : "missing",
      visibleRows: player
        ? player.lines.filter(function (line) {
            return line.row.dataset.visible === "true";
          }).length
        : 0
    };
  }

  function diagnoseTerminals() {
    var enhanced = Array.prototype.slice.call(document.querySelectorAll(".talika-terminal--enhanced"));

    return {
      reducedMotion: reducedMotion.matches,
      sourceMatches: document.querySelectorAll(TERMINAL_SELECTOR).length,
      enhanced: enhanced.length,
      players: enhanced.map(function (node, index) {
        return diagnosePlayer(node.__talikaTerminalPlayer, index);
      })
    };
  }

  function replayAll() {
    document.querySelectorAll(".talika-terminal--enhanced").forEach(function (node) {
      var player = node.__talikaTerminalPlayer;

      if (player) {
        play(player.lines, player.state, player.replay, true);
      }
    });
  }

  function replayFirst() {
    var first = document.querySelector(".talika-terminal--enhanced");
    var player = first ? first.__talikaTerminalPlayer : null;

    if (player) {
      play(player.lines, player.state, player.replay, true);
    }
  }

  function debug(label, payload) {
    if (!isDebugEnabled() || !window.console) {
      return;
    }

    window.console.debug("[TalikaTerminal] " + label, payload || "");
  }

  function isDebugEnabled() {
    try {
      return window.location.search.indexOf("talikaTerminalDebug=1") !== -1 || localStorage.getItem(DEBUG_KEY) === "1";
    } catch (error) {
      return false;
    }
  }

  window.TalikaTerminal = {
    diagnose: diagnoseTerminals,
    init: initTalikaTerminals,
    replayAll: replayAll,
    replayFirst: replayFirst
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTalikaTerminals);
  } else {
    initTalikaTerminals();
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(initTalikaTerminals);
  }
})();
