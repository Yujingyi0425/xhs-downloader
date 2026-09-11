/* 由 apps/extension/build.mjs 生成，请勿手工修改。 */
"use strict";
(() => {
  // src/browser-state-bridge.ts
  var REQUEST_EVENT = "xhd-browser-state-request";
  var RESPONSE_EVENT = "xhd-browser-state-response";
  function readLiveInitialState(page, timeoutMilliseconds = 1e3) {
    const scope = page.defaultView;
    if (!scope) return Promise.reject(new Error("\u5F53\u524D\u9875\u9762\u6CA1\u6709\u53EF\u7528\u7A97\u53E3"));
    const requestId = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timeout = scope.setTimeout(() => {
        scope.removeEventListener(RESPONSE_EVENT, onResponse);
        reject(new Error("\u8BFB\u53D6\u5C0F\u7EA2\u4E66\u5B9E\u65F6\u72B6\u6001\u8D85\u65F6"));
      }, timeoutMilliseconds);
      const onResponse = (event) => {
        const response = parseResponse(event.detail);
        if (!response || response.requestId !== requestId) return;
        scope.clearTimeout(timeout);
        scope.removeEventListener(RESPONSE_EVENT, onResponse);
        if (!response.ok || !response.data) {
          reject(new Error(response.message || "\u5C0F\u7EA2\u4E66\u5B9E\u65F6\u72B6\u6001\u4E0D\u53EF\u7528"));
          return;
        }
        try {
          resolve(JSON.parse(response.data));
        } catch {
          reject(new Error("\u5C0F\u7EA2\u4E66\u5B9E\u65F6\u72B6\u6001\u683C\u5F0F\u65E0\u6548"));
        }
      };
      scope.addEventListener(RESPONSE_EVENT, onResponse);
      scope.dispatchEvent(
        new CustomEvent(REQUEST_EVENT, {
          detail: JSON.stringify({ requestId })
        })
      );
    });
  }
  function browserStateEvents() {
    return { request: REQUEST_EVENT, response: RESPONSE_EVENT };
  }
  function parseResponse(value) {
    if (typeof value !== "string") return null;
    try {
      const parsed = JSON.parse(value);
      return typeof parsed.requestId === "string" ? parsed : null;
    } catch {
      return null;
    }
  }

  // src/current-account-navigation.ts
  var CURRENT_USER_CHANNEL_SELECTOR = ".main-container .user .link-wrapper .channel";
  var PROFILE_PATH = /^\/user\/profile\/([^/?#]+)\/?$/;
  function isValidAccountId(value) {
    return value.length >= 1 && value.length <= 128;
  }
  function readCurrentNavigationAccountId(page) {
    const channel = page.querySelector(CURRENT_USER_CHANNEL_SELECTOR);
    const link = channel?.closest("a[href]");
    const rawHref = link?.getAttribute("href");
    if (!rawHref) return "";
    try {
      const url = new URL(rawHref, page.baseURI);
      if (url.protocol !== "https:" || url.hostname !== "www.xiaohongshu.com" || !["", "443"].includes(url.port)) {
        return "";
      }
      const match = PROFILE_PATH.exec(url.pathname);
      if (!match) return "";
      const accountId = decodeURIComponent(match[1]);
      return isValidAccountId(accountId) ? accountId : "";
    } catch {
      return "";
    }
  }

  // src/parser.ts
  var EPHEMERAL_IMAGE_ROUTE = /^\d{12}\/[0-9a-f]{32}\//i;
  function parseInitialStateScript(script, sourceUrl) {
    const state = parseInitialStateValue(script);
    return parseInitialStateRecord(state, sourceUrl);
  }
  function parseInitialStateRecord(state, sourceUrl) {
    const workId = workIdFromUrl(sourceUrl);
    const note = selectNote(state, workId);
    const resolvedWorkId = text(note.noteId) || workId;
    const user = object(note.user);
    const authorId = text(user.userId);
    const images = list(note.imageList);
    const video = object(note.video);
    const kind = text(note.type);
    const media = kind === "video" && images.length <= 1 ? parseVideo(video, images) : parseImages(images);
    return {
      workId: resolvedWorkId,
      sourceUrl,
      title: text(note.title),
      description: text(note.desc),
      authorName: text(user.nickname) || text(user.nickName) || authorId,
      authorAvatar: text(user.avatar) || text(user.image) || void 0,
      media
    };
  }
  function parseInitialStateValue(script) {
    const separator = script.indexOf("=");
    if (separator < 0) throw new Error("\u5E16\u5B50\u521D\u59CB\u72B6\u6001\u683C\u5F0F\u65E0\u6548");
    const raw = script.slice(separator + 1).trim().replace(/;$/, "").replace(/\bnew\s+Map\s*\(\s*\[\s*\]\s*\)/g, "{}");
    let state;
    try {
      state = JSON.parse(normalizeJavaScriptValue(raw));
    } catch {
      throw new Error("\u5E16\u5B50\u521D\u59CB\u72B6\u6001\u65E0\u6CD5\u89E3\u6790");
    }
    return state;
  }
  function selectNote(state, workId) {
    const noteMap = object(deepGet(state, "note.noteDetailMap"));
    const direct = object(noteMap[workId]);
    const directNote = object(direct.note);
    if (noteMatches(directNote, workId)) return directNote;
    const matchingNote = Object.values(noteMap).map((wrapper) => object(object(wrapper).note)).find((note) => noteMatches(note, workId));
    if (matchingNote) return matchingNote;
    const phoneNote = object(deepGet(state, "noteData.data.noteData"));
    if (noteMatches(phoneNote, workId)) return phoneNote;
    if (hasKeys(noteMap) || hasKeys(phoneNote)) {
      throw new Error("\u9875\u9762\u5E16\u5B50\u6570\u636E\u4E0E\u5F53\u524D\u94FE\u63A5\u4E0D\u4E00\u81F4\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5");
    }
    throw new Error("\u5F53\u524D\u9875\u9762\u6CA1\u6709\u53EF\u89E3\u6790\u7684\u5E16\u5B50\u6570\u636E");
  }
  function noteMatches(note, workId) {
    return hasKeys(note) && text(note.noteId) === workId;
  }
  function parseVideo(video, images) {
    const originKey = text(deepGet(video, "consumer.originVideoKey"));
    const url = originKey ? `https://sns-video-bd.xhscdn.com/${originKey}` : selectVideoStream(video);
    if (!url) return [];
    const preview = text(images[0]?.urlDefault) || text(images[0]?.url);
    return [
      {
        index: 1,
        kind: "video",
        url: decodeUrl(url),
        suffix: "mp4",
        previewUrl: preview ? stableImageUrl(preview) : void 0
      }
    ];
  }
  function selectVideoStream(video) {
    const streams = videoStreamVariants(video);
    const selected = streams.sort((left, right) => number(right.height) - number(left.height))[0];
    const backups = Array.isArray(selected?.backupUrls) ? selected.backupUrls : [];
    return backups.find((item) => typeof item === "string" && !!item) || text(selected?.masterUrl) || text(selected?.url) || text(selected?.playUrl) || text(selected?.downloadUrl);
  }
  function videoStreamVariants(video) {
    const stream = object(deepGet(video, "media.stream"));
    const direct = hasVideoLocatorFields(stream) ? [stream] : [];
    const nested = Object.values(stream).flatMap((value) => {
      if (Array.isArray(value)) return value.map(object).filter(hasVideoLocatorFields);
      const candidate = object(value);
      return hasVideoLocatorFields(candidate) ? [candidate] : [];
    });
    return [...direct, ...nested];
  }
  function hasVideoLocatorFields(value) {
    return ["masterUrl", "url", "playUrl", "downloadUrl"].some(
      (field) => text(value[field])
    ) || Array.isArray(value.backupUrls);
  }
  function parseImages(images) {
    return images.flatMap((image, position) => {
      const index = position + 1;
      const result = [];
      const imageUrl = text(image.urlDefault) || text(image.url);
      if (imageUrl) {
        result.push({
          index,
          kind: "image",
          url: stableImageUrl(imageUrl),
          suffix: imageSuffix(imageUrl)
        });
      }
      const liveUrl = text(deepGet(image, "stream.h264.0.masterUrl"));
      if (liveUrl) {
        result.push({
          index,
          kind: "live",
          url: decodeUrl(liveUrl),
          suffix: "mp4",
          previewUrl: imageUrl ? stableImageUrl(imageUrl) : void 0
        });
      }
      return result;
    });
  }
  function stableImageUrl(value) {
    const parsed = new URL(decodeUrl(value));
    const path = parsed.pathname.replace(/^\//, "").replace(EPHEMERAL_IMAGE_ROUTE, "").split("!", 1)[0];
    return `https://sns-img-bd.xhscdn.com/${path}`;
  }
  function inspectInitialStateVideo(state, sourceUrl) {
    let note;
    try {
      note = selectNote(state, workIdFromUrl(sourceUrl));
    } catch {
      return {
        video_object_present: false,
        video_keys_class: "EMPTY",
        video_stream_object_present: false,
        video_variant_count: 0
      };
    }
    const rawVideo = note.video;
    const video = object(rawVideo);
    const media = object(video.media);
    const stream = object(media.stream);
    const variants = videoStreamVariants(video);
    const consumer = object(video.consumer);
    const knownFields = ["url", "src", "playAddr", "downloadAddr", "originVideoKey"].some(
      (field) => text(video[field]) || text(consumer[field])
    );
    return {
      video_object_present: hasKeys(video),
      video_keys_class: !hasKeys(video) ? "EMPTY" : hasKeys(consumer) ? "CONSUMER" : hasKeys(media) ? "MEDIA" : knownFields ? "KNOWN_FIELDS" : "OTHER",
      video_stream_object_present: hasKeys(stream),
      video_variant_count: variants.length
    };
  }
  function normalizeFeedImageUrl(value) {
    try {
      const decoded = decodeUrl(value);
      const parsed = new URL(decoded);
      if (parsed.hostname.startsWith("sns-webpic-") && parsed.hostname.endsWith(".xhscdn.com")) {
        return stableImageUrl(decoded);
      }
      return parsed.toString();
    } catch {
      return value;
    }
  }
  function imageSuffix(value) {
    const match = decodeUrl(value).match(/_(avif|heic|jpeg|jpg|png|webp)(?:_|$)/i);
    const suffix = match?.[1]?.toLowerCase();
    return suffix === "jpg" ? "jpeg" : suffix || "jpeg";
  }
  function normalizeJavaScriptValue(value) {
    let result = "";
    let quote = "";
    let escaped = false;
    for (let index = 0; index < value.length; index += 1) {
      const character = value[index];
      if (quote) {
        result += character;
        if (escaped) escaped = false;
        else if (character === "\\") escaped = true;
        else if (character === quote) quote = "";
        continue;
      }
      if (character === '"' || character === "'") {
        quote = character;
        result += character;
        continue;
      }
      const token = value.slice(index, index + 9);
      if (token === "undefined" && isBoundary(value[index - 1]) && isBoundary(value[index + 9])) {
        result += "null";
        index += 8;
        continue;
      }
      result += character;
    }
    return result;
  }
  function isBoundary(value) {
    return !value || !/[A-Za-z0-9_$]/.test(value);
  }
  function workIdFromUrl(value) {
    const parts = new URL(value).pathname.split("/").filter(Boolean);
    return parts.at(-1) ?? "";
  }
  function deepGet(value, path) {
    return path.split(".").reduce((current, segment) => {
      if (Array.isArray(current)) return current[Number(segment)];
      return object(current)[segment];
    }, value);
  }
  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }
  function list(value) {
    return Array.isArray(value) ? value.map(object).filter(hasKeys) : [];
  }
  function hasKeys(value) {
    return Object.keys(value).length > 0;
  }
  function text(value) {
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
  }
  function number(value) {
    const result = Number(value);
    return Number.isFinite(result) ? result : 0;
  }
  function decodeUrl(value) {
    return value.replaceAll("\\u002F", "/").replaceAll("\\/", "/").replaceAll("\\u0026", "&");
  }

  // src/page-data.ts
  var INITIAL_STATE_PREFIX = "window.__INITIAL_STATE__";
  function latestInitialState(page) {
    const scripts = [...page.scripts].map((script) => script.textContent?.trim() ?? "").filter((value) => value.startsWith(INITIAL_STATE_PREFIX)).reverse();
    for (const script of scripts) {
      try {
        return parseInitialStateValue(script);
      } catch {
      }
    }
    throw new Error("\u5F53\u524D\u9875\u9762\u6CA1\u6709\u53EF\u89E3\u6790\u7684\u5C0F\u7EA2\u4E66\u72B6\u6001\u6570\u636E");
  }
  function dataRecord(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }
  function dataList(value) {
    return Array.isArray(value) ? value : [];
  }
  function unwrapState(value) {
    const object3 = dataRecord(value);
    if ("value" in object3) return object3.value;
    if ("_value" in object3) return object3._value;
    return value;
  }
  function dataText(value) {
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
  }
  function dataInteger(value) {
    const result = Number(value);
    return Number.isFinite(result) && result >= 0 ? Math.trunc(result) : null;
  }
  function dataBoolean(value, fallback = false) {
    return typeof value === "boolean" ? value : fallback;
  }
  function dataUrl(value) {
    const raw = dataText(value);
    try {
      const url = new URL(raw);
      return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
    } catch {
      return null;
    }
  }

  // src/account-proof.ts
  var PROOF_CONTEXT = "xhs-account-challenge/v1\0";
  async function proveBrowserAccount(page, challenge) {
    if (!/^[0-9a-f]{32}$/.test(challenge.challengeId)) {
      return { status: "unverified" };
    }
    let state = {};
    try {
      state = await readLiveInitialState(page);
    } catch {
    }
    const user = dataRecord(state.user);
    const info = dataRecord(unwrapState(user.userInfo));
    if (info.guest === true) return { status: "logged_out" };
    const stateAccountId = dataText(info.userId ?? info.user_id);
    const accountId = info.guest === false && isValidAccountId(stateAccountId) ? stateAccountId : readCurrentNavigationAccountId(page);
    if (!accountId) {
      return { status: "unverified" };
    }
    try {
      return {
        status: "proved",
        proof: await hmacProof(challenge, accountId)
      };
    } catch {
      return { status: "unverified" };
    }
  }
  async function hmacProof(challenge, accountId) {
    const key = await crypto.subtle.importKey(
      "raw",
      decodeBase64Url(challenge.challengeKey),
      { hash: "SHA-256", name: "HMAC" },
      false,
      ["sign"]
    );
    const message = new TextEncoder().encode(
      `${PROOF_CONTEXT}${challenge.challengeId}\0${accountId}`
    );
    const digest = await crypto.subtle.sign("HMAC", key, message);
    return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  }
  function decodeBase64Url(value) {
    const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized.padEnd(normalized.length + (4 - normalized.length % 4) % 4, "=");
    const decoded = atob(padded);
    const buffer = new ArrayBuffer(decoded.length);
    const bytes = new Uint8Array(buffer);
    for (let index = 0; index < decoded.length; index += 1) {
      bytes[index] = decoded.charCodeAt(index);
    }
    return buffer;
  }

  // src/browser-action-errors.ts
  var UncertainBrowserActionError = class extends Error {
    constructor(message) {
      super(message);
      this.name = "UncertainBrowserActionError";
    }
  };

  // src/browser-page-diagnostics.ts
  var ADAPTER_VERSION = "xhs-web-2026.07";
  var COMMON_ANCHORS = {
    initial_state: "script",
    main_container: ".main-container"
  };
  var PAGE_ANCHORS = {
    home: {
      feed_container: ".feeds-container, [class*='feeds-container']"
    },
    search: {
      filter_control: ".filter, [class*='filter']",
      feed_container: ".feeds-container, [class*='feeds-container']"
    },
    feed_detail: {
      comment_container: ".comments-container",
      detail_container: ".note-detail-mask, [class*='note-detail']"
    },
    profile: {
      profile_container: ".user-page, [class*='user-page']"
    }
  };
  function buildPageCompatibilityDiagnostics(page, pageUrl) {
    const pageKind = classifyPage(pageUrl);
    const expected = {
      ...COMMON_ANCHORS,
      ...PAGE_ANCHORS[pageKind] ?? {}
    };
    const matched = Object.entries(expected).filter(
      ([name, selector]) => name === "initial_state" ? hasInitialStateScript(page) : Boolean(page.querySelector(selector))
    ).map(([name]) => name);
    const missing = Object.keys(expected).filter((name) => !matched.includes(name));
    return {
      adapter_version: ADAPTER_VERSION,
      selector_profile: detectSelectorProfile(page),
      page_kind: pageKind,
      matched_anchors: matched,
      missing_anchors: missing
    };
  }
  function classifyPage(value) {
    try {
      const pathname = new URL(value).pathname;
      if (pathname.startsWith("/search_result")) return "search";
      if (pathname.startsWith("/user/profile/")) return "profile";
      if (pathname.startsWith("/explore/") || pathname.startsWith("/discovery/item/")) {
        return "feed_detail";
      }
      if (pathname === "/" || pathname.startsWith("/explore")) return "home";
    } catch {
      return "unknown";
    }
    return "unknown";
  }
  function detectSelectorProfile(page) {
    if (hasInitialStateScript(page)) return "initial-state-v1";
    if (page.querySelector(".main-container, #global")) return "semantic-dom-v1";
    return "unknown";
  }
  function hasInitialStateScript(page) {
    return [...page.scripts].some((script) => script.textContent?.includes("__INITIAL_STATE__"));
  }

  // src/login-state.ts
  var LOGIN_SELECTOR = ".login-container, [class*='login-container']";
  var INITIAL_STATE_PREFIX2 = "window.__INITIAL_STATE__";
  function detectLoginState(page, pageUrl) {
    const user = readCurrentUser(page);
    const stateAccountId = text2(user?.userId ?? user?.user_id);
    const stateLoggedIn = user?.guest === false && isValidAccountId(stateAccountId);
    const navigationAccountId = readCurrentNavigationAccountId(page);
    const loginVisible = new URL(pageUrl).pathname.includes("login") || Boolean(page.querySelector(LOGIN_SELECTOR));
    const accountId = stateLoggedIn ? stateAccountId : navigationAccountId;
    const loggedIn = Boolean(accountId) && !loginVisible;
    return {
      logged_in: loggedIn,
      user_id: loggedIn ? accountId : null,
      nickname: loggedIn ? text2(user?.nickname ?? user?.nickName) || null : null
    };
  }
  function readCurrentUser(page) {
    const scripts = [...page.scripts].map((script) => script.textContent?.trim() ?? "").filter((value) => value.startsWith(INITIAL_STATE_PREFIX2)).reverse();
    for (const script of scripts) {
      try {
        const state = object2(parseInitialStateValue(script));
        const user = object2(state.user);
        const rawInfo = object2(user.userInfo);
        const info = object2(rawInfo.value ?? rawInfo);
        if (Object.keys(info).length) return info;
      } catch {
      }
    }
    return void 0;
  }
  function object2(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }
  function text2(value) {
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
  }

  // src/login-qrcode.ts
  var QR_VALIDITY_MILLISECONDS = 4 * 60 * 1e3;
  var QR_WAIT_MILLISECONDS = 1e4;
  var QR_POLL_INTERVAL_MILLISECONDS = 250;
  var MAX_QR_DATA_URL_LENGTH = 512e3;
  var QR_DATA_PATTERN = /^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=\r\n]+$/;
  var QR_IMAGE_SELECTOR = [
    ".login-container .qrcode-img",
    '.login-container img[class*="qrcode"]',
    '.login-container img[alt*="\u4E8C\u7EF4\u7801"]'
  ].join(",");
  function readLoginQrCode(page, pageUrl, now = /* @__PURE__ */ new Date()) {
    if (detectLoginState(page, pageUrl).logged_in) {
      return {
        is_logged_in: true,
        image_data_url: null,
        expires_at: null,
        consumed: false
      };
    }
    const image = page.querySelector(QR_IMAGE_SELECTOR);
    const source = image?.currentSrc || image?.getAttribute("src") || "";
    if (!source || source.length > MAX_QR_DATA_URL_LENGTH || !QR_DATA_PATTERN.test(source)) {
      throw new Error("\u767B\u5F55\u9875\u6CA1\u6709\u53EF\u5B89\u5168\u4EA4\u4ED8\u7684\u4E8C\u7EF4\u7801\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5");
    }
    return {
      is_logged_in: false,
      image_data_url: source,
      expires_at: new Date(now.getTime() + QR_VALIDITY_MILLISECONDS).toISOString(),
      consumed: false
    };
  }
  async function waitForLoginQrCode(page, pageUrl, timeoutMilliseconds = QR_WAIT_MILLISECONDS, pollIntervalMilliseconds = QR_POLL_INTERVAL_MILLISECONDS) {
    const deadline = Date.now() + timeoutMilliseconds;
    let lastError;
    do {
      try {
        return readLoginQrCode(page, pageUrl);
      } catch (error) {
        lastError = error;
      }
      await delay(pollIntervalMilliseconds);
    } while (Date.now() < deadline);
    throw lastError instanceof Error ? lastError : new Error("\u767B\u5F55\u9875\u6CA1\u6709\u53EF\u5B89\u5168\u4EA4\u4ED8\u7684\u4E8C\u7EF4\u7801\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5");
  }
  function delay(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/comment-loader.ts
  var COMMENT_SELECTOR = ".comments-container .parent-comment";
  var END_SELECTOR = ".comments-container .end-container, .comments-container .no-more";
  function needsCommentLoading(options) {
    return options.commentLimit > 10 || options.includeReplies;
  }
  async function loadComments(page, options) {
    if (!needsCommentLoading(options) || options.commentLimit === 0) return;
    const container = await waitForCommentContainer(page);
    if (!container) throw new Error("\u8BE6\u60C5\u9875\u8BC4\u8BBA\u533A\u5C1A\u672A\u52A0\u8F7D");
    const maxAttempts = Math.min(30, Math.max(4, options.commentLimit + 2));
    let stagnantRounds = 0;
    let previousCount = -1;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const comments = [...page.querySelectorAll(COMMENT_SELECTOR)];
      if (options.includeReplies) {
        expandReplies(comments, options.replyLimit);
      }
      if (comments.length >= options.commentLimit || page.querySelector(END_SELECTOR)) {
        return;
      }
      stagnantRounds = comments.length === previousCount ? stagnantRounds + 1 : 0;
      if (stagnantRounds >= 4) return;
      previousCount = comments.length;
      const last = comments.at(-1);
      last?.scrollIntoView?.({ block: "end" });
      container.scrollTop = container.scrollHeight;
      page.defaultView?.scrollBy(0, page.defaultView.innerHeight * 0.8);
      await delay2(250);
    }
  }
  async function waitForCommentContainer(page) {
    const findContainer = () => page.querySelector(".comments-container, [class*='comments-container']");
    let container = findContainer();
    if (container || !page.defaultView) return container;
    page.defaultView.scrollBy(0, page.defaultView.innerHeight * 0.8);
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await delay2(250);
      container = findContainer();
      if (container) return container;
    }
    return null;
  }
  function expandReplies(comments, replyLimit) {
    if (replyLimit <= 0) return;
    let clicked = 0;
    for (const comment of comments) {
      if (clicked >= replyLimit) return;
      const control = comment.querySelector(".show-more");
      if (!control || control.dataset.xhdExpanded === "true") continue;
      control.dataset.xhdExpanded = "true";
      control.click();
      clicked += 1;
    }
  }
  function delay2(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/comment-runner.ts
  var COMMENT_ELEMENTS = ".comments-container .parent-comment, .comments-container .comment-item";
  async function postComment(page, feedId, content) {
    return submitComment(page, feedId, content);
  }
  async function replyComment(page, feedId, content, target) {
    const comment = await findTargetCommentWithLoading(page, target);
    if (!comment) throw new Error("\u8BC4\u8BBA\u533A\u6CA1\u6709\u627E\u5230\u56DE\u590D\u76EE\u6807");
    comment.scrollIntoView?.({ block: "center" });
    const reply = comment.querySelector(
      ".right .interactions .reply, .interactions .reply, .reply"
    );
    if (!reply) throw new Error("\u76EE\u6807\u8BC4\u8BBA\u6CA1\u6709\u56DE\u590D\u6309\u94AE");
    reply.click();
    await delay3(150);
    return submitComment(page, feedId, content);
  }
  async function findTargetCommentWithLoading(page, target) {
    const container = page.querySelector(".comments-container");
    for (let attempt = 0; attempt < 24; attempt += 1) {
      const match = findTargetComment(page, target);
      if (match) return match;
      if (!container || page.querySelector(".comments-container .end-container, .comments-container .no-more")) {
        return null;
      }
      const comments = page.querySelectorAll(COMMENT_ELEMENTS);
      comments.item(comments.length - 1)?.scrollIntoView?.({ block: "end" });
      container.scrollTop = container.scrollHeight;
      page.defaultView?.scrollBy(0, page.defaultView.innerHeight * 0.8);
      await delay3(250);
    }
    return null;
  }
  async function submitComment(page, feedId, content) {
    const before = matchingComments(page, content).length;
    const input = await waitForCommentInput(page);
    if (!input) throw new Error("\u9875\u9762\u6CA1\u6709\u53EF\u7528\u7684\u8BC4\u8BBA\u8F93\u5165\u6846");
    fillContentEditable(page, input, content);
    const submit = await waitForEnabledSubmit(page);
    if (!submit) throw new Error("\u8BC4\u8BBA\u63D0\u4EA4\u6309\u94AE\u5F53\u524D\u4E0D\u53EF\u7528");
    submit.click();
    for (let attempt = 0; attempt < 16; attempt += 1) {
      const matches = matchingComments(page, content);
      if (matches.length > before) {
        return {
          feed_id: feedId,
          comment_id: commentId(matches.at(-1) ?? null),
          verified: true
        };
      }
      await delay3(250);
    }
    throw new UncertainBrowserActionError("\u8BC4\u8BBA\u63D0\u4EA4\u5DF2\u89E6\u53D1\uFF0C\u4F46\u672A\u5728\u8BC4\u8BBA\u533A\u786E\u8BA4\u7ED3\u679C\uFF0C\u8BF7\u4EBA\u5DE5\u6838\u5BF9");
  }
  async function waitForCommentInput(page) {
    let activated = false;
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const activator = page.querySelector("div.input-box div.content-edit span");
      if (activator && !activated) {
        activator.click();
        activated = true;
        await delay3(150);
      }
      const input = page.querySelector(
        "div.input-box div.content-edit p.content-input, div.input-box [contenteditable='true']"
      );
      if (input) return input;
      await delay3(250);
    }
    return null;
  }
  function findTargetComment(page, target) {
    if (target.commentId) {
      const direct = page.getElementById(`comment-${target.commentId}`);
      if (direct instanceof HTMLElement) return direct;
    }
    if (!target.userId) return null;
    return [...page.querySelectorAll(COMMENT_ELEMENTS)].find(
      (item) => [...item.querySelectorAll("[data-user-id]")].some(
        (user) => user.dataset.userId === target.userId
      )
    ) ?? null;
  }
  function fillContentEditable(page, input, content) {
    input.focus();
    const scope = page.defaultView;
    const selection = scope?.getSelection();
    if (selection) {
      const range = page.createRange();
      range.selectNodeContents(input);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    }
    if (typeof page.execCommand === "function" && page.execCommand("insertText", false, content)) {
      return;
    }
    const beforeInput = scope ? new scope.InputEvent("beforeinput", {
      bubbles: true,
      cancelable: true,
      inputType: "insertText",
      data: content
    }) : new Event("beforeinput", { bubbles: true, cancelable: true });
    if (!input.dispatchEvent(beforeInput)) return;
    input.textContent = content;
    const event = scope ? new scope.InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: content
    }) : new Event("input", { bubbles: true });
    input.dispatchEvent(event);
  }
  async function waitForEnabledSubmit(page) {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const submit = page.querySelector("div.bottom button.submit");
      if (submit && !submit.disabled) return submit;
      await delay3(100);
    }
    return null;
  }
  function matchingComments(page, content) {
    const expected = normalize(content);
    return [...page.querySelectorAll(COMMENT_ELEMENTS)].filter(
      (item) => normalize(item.textContent ?? "").includes(expected)
    );
  }
  function commentId(element) {
    if (!element) return null;
    return element.dataset.commentId ?? (element.id.startsWith("comment-") ? element.id.slice(8) : null);
  }
  function normalize(value) {
    return value.replace(/\s+/g, " ").trim();
  }
  function delay3(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/feed-parser.ts
  function parseFeedListDocument(page, source, keyword = null, currentState) {
    const state = currentState ?? latestInitialState(page);
    const container = dataRecord(state[source === "home" ? "feed" : "search"]);
    if (!("feeds" in container)) {
      throw new Error(source === "home" ? "\u63A8\u8350\u6D41\u5C1A\u672A\u52A0\u8F7D" : "\u641C\u7D22\u7ED3\u679C\u5C1A\u672A\u52A0\u8F7D");
    }
    return {
      items: parseFeedSummaries(unwrapState(container.feeds)).slice(0, 200),
      source,
      keyword: source === "search" ? keyword : null,
      has_more: dataBoolean(container.hasMore ?? container.has_more),
      cursor: dataText(container.cursor).slice(0, 2048)
    };
  }
  function parseFeedSummaries(value) {
    return flattenFeeds(value).map(parseFeedSummary).filter((item) => item !== null);
  }
  function parseFeedAuthor(value) {
    const user = dataRecord(value);
    const userId = dataText(user.userId ?? user.user_id);
    if (!userId) return null;
    return {
      user_id: userId,
      nickname: dataText(user.nickname ?? user.nickName).slice(0, 200),
      avatar_url: dataUrl(user.avatar ?? user.image)
    };
  }
  function parseFeedMetrics(value) {
    const metrics = dataRecord(value);
    return {
      liked: dataBoolean(metrics.liked),
      liked_count: dataText(metrics.likedCount) || "0",
      collected: dataBoolean(metrics.collected),
      collected_count: dataText(metrics.collectedCount) || "0",
      comment_count: dataText(metrics.commentCount) || "0",
      shared_count: dataText(metrics.sharedCount) || "0"
    };
  }
  function parseFeedSummary(value) {
    const feed = dataRecord(value);
    const note = dataRecord(feed.noteCard);
    const author = parseFeedAuthor(note.user);
    const feedId = dataText(feed.id ?? note.noteId);
    if (!feedId || !author) return null;
    const cover = dataRecord(note.cover);
    const video = dataRecord(note.video);
    const capability = dataRecord(video.capa);
    return {
      feed_id: feedId,
      xsec_token: dataText(feed.xsecToken ?? note.xsecToken),
      title: dataText(note.displayTitle ?? note.title).slice(0, 500),
      note_type: noteType(note.type),
      author,
      metrics: parseFeedMetrics(note.interactInfo),
      cover_url: dataUrl(cover.urlDefault ?? cover.urlPre ?? cover.url),
      cover_width: dataInteger(cover.width),
      cover_height: dataInteger(cover.height),
      video_duration: dataInteger(capability.duration)
    };
  }
  function flattenFeeds(value) {
    return dataList(value).flatMap((item) => Array.isArray(item) ? flattenFeeds(item) : [item]);
  }
  function noteType(value) {
    const type = dataText(value).toLowerCase();
    if (type === "video") return "video";
    if (type === "normal" || type === "image") return "image";
    return "unknown";
  }

  // src/feed-detail-parser-telemetry.ts
  var FeedDetailParserError = class extends Error {
    constructor(message, telemetry) {
      super(message);
      this.telemetry = telemetry;
      this.name = "FeedDetailParserError";
    }
    telemetry;
  };
  var ParserTelemetryBuilder = class {
    initial_state_anchor_present;
    initial_state_parse_result = "MISSING";
    note_root_present = false;
    note_detail_map_present = false;
    note_detail_map_count = 0;
    target_wrapper_found = false;
    target_wrapper_match_mode = "NOT_REACHED";
    target_note_present = false;
    target_note_id_match = false;
    author_object_present = false;
    author_id_present = false;
    image_list_present = false;
    image_list_length = 0;
    normalized_note_type = "NOT_REACHED";
    last_completed_parser_boundary = "NONE";
    parser_failure_subtype = "NONE";
    safe_exception_class = "NONE";
    constructor(initialStateAnchorPresent) {
      this.initial_state_anchor_present = initialStateAnchorPresent;
    }
    complete(boundary) {
      this.last_completed_parser_boundary = boundary;
    }
    fail(subtype, message, exception) {
      this.parser_failure_subtype = subtype;
      this.safe_exception_class = exception;
      throw new FeedDetailParserError(message, this.snapshot());
    }
    snapshot() {
      return {
        initial_state_anchor_present: this.initial_state_anchor_present,
        initial_state_parse_result: this.initial_state_parse_result,
        note_root_present: this.note_root_present,
        note_detail_map_present: this.note_detail_map_present,
        note_detail_map_count: this.note_detail_map_count,
        target_wrapper_found: this.target_wrapper_found,
        target_wrapper_match_mode: this.target_wrapper_match_mode,
        target_note_present: this.target_note_present,
        target_note_id_match: this.target_note_id_match,
        author_object_present: this.author_object_present,
        author_id_present: this.author_id_present,
        image_list_present: this.image_list_present,
        image_list_length: this.image_list_length,
        normalized_note_type: this.normalized_note_type,
        last_completed_parser_boundary: this.last_completed_parser_boundary,
        parser_failure_subtype: this.parser_failure_subtype,
        safe_exception_class: this.safe_exception_class
      };
    }
  };
  function hasInitialStateAnchor(page) {
    return [...page.scripts].some(
      (script) => script.textContent?.trim().startsWith("window.__INITIAL_STATE__")
    );
  }
  function isRecordValue(value) {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
  }
  function boundedCount(value) {
    return Math.min(Math.max(0, Math.trunc(value)), 1e3);
  }
  function normalizedNoteType(value) {
    const type = typeof value === "string" ? value.toLowerCase() : "";
    if (type === "video") return "VIDEO";
    if (type === "normal" || type === "image") return "IMAGE";
    return "UNKNOWN";
  }
  function exceptionClass(error) {
    if (error instanceof TypeError) return "TypeError";
    if (error instanceof SyntaxError) return "SyntaxError";
    if (error instanceof Error) return "Error";
    return "Unknown";
  }

  // src/feed-detail-parser.ts
  function parseFeedDetailDocumentWithTelemetry(page, options, currentState) {
    const telemetry = new ParserTelemetryBuilder(hasInitialStateAnchor(page));
    try {
      let state;
      try {
        state = currentState ?? latestInitialState(page);
      } catch (error) {
        telemetry.initial_state_parse_result = telemetry.initial_state_anchor_present ? "INVALID" : "MISSING";
        telemetry.fail(
          telemetry.initial_state_anchor_present ? "INITIAL_STATE_PARSE_FAILED" : "INITIAL_STATE_MISSING",
          "\u5F53\u524D\u9875\u9762\u6CA1\u6709\u53EF\u89E3\u6790\u7684\u5C0F\u7EA2\u4E66\u72B6\u6001\u6570\u636E",
          exceptionClass(error)
        );
      }
      if (!isRecordValue(state)) {
        telemetry.initial_state_parse_result = "UNEXPECTED_SHAPE";
        telemetry.fail(
          "INITIAL_STATE_PARSE_FAILED",
          "\u5F53\u524D\u9875\u9762\u6CA1\u6709\u53EF\u89E3\u6790\u7684\u5C0F\u7EA2\u4E66\u72B6\u6001\u6570\u636E",
          "Error"
        );
      }
      const stateRecord = state;
      telemetry.initial_state_parse_result = "PARSED";
      telemetry.complete("INITIAL_STATE_PARSED");
      const noteRoot = stateRecord.note;
      const noteState = dataRecord(noteRoot);
      telemetry.note_root_present = isRecordValue(noteRoot);
      if (!telemetry.note_root_present) {
        telemetry.fail("NOTE_ROOT_MISSING", "\u8BE6\u60C5\u9875\u6CA1\u6709\u8BF7\u6C42\u7684\u5E16\u5B50\u6570\u636E", "Error");
      }
      telemetry.complete("NOTE_ROOT_FOUND");
      const detailMapValue = noteState.noteDetailMap;
      const detailMap = dataRecord(detailMapValue);
      telemetry.note_detail_map_present = isRecordValue(detailMapValue);
      telemetry.note_detail_map_count = boundedCount(Object.keys(detailMap).length);
      if (!telemetry.note_detail_map_present || telemetry.note_detail_map_count === 0) {
        telemetry.fail("NOTE_DETAIL_MAP_MISSING", "\u8BE6\u60C5\u9875\u6CA1\u6709\u8BF7\u6C42\u7684\u5E16\u5B50\u6570\u636E", "Error");
      }
      telemetry.complete("NOTE_DETAIL_MAP_FOUND");
      const located = findDetail(detailMap, options.feedId);
      if (!located) {
        telemetry.target_wrapper_match_mode = "NONE";
        telemetry.fail("TARGET_WRAPPER_NOT_FOUND", "\u8BE6\u60C5\u9875\u6CA1\u6709\u8BF7\u6C42\u7684\u5E16\u5B50\u6570\u636E", "Error");
      }
      const locatedRecord = located;
      telemetry.target_wrapper_found = true;
      telemetry.target_wrapper_match_mode = locatedRecord.matchMode;
      telemetry.complete("TARGET_WRAPPER_FOUND");
      const noteValue = locatedRecord.wrapper.note;
      const note = dataRecord(noteValue);
      telemetry.target_note_present = isRecordValue(noteValue);
      if (!telemetry.target_note_present) {
        telemetry.fail("TARGET_NOTE_MISSING", "\u8BE6\u60C5\u9875\u6570\u636E\u4E0E\u8BF7\u6C42\u7684\u5E16\u5B50\u4E0D\u4E00\u81F4", "Error");
      }
      telemetry.complete("TARGET_NOTE_FOUND");
      const noteId = dataText(note.noteId);
      telemetry.target_note_id_match = noteId === options.feedId;
      if (!telemetry.target_note_id_match) {
        telemetry.fail("TARGET_NOTE_ID_MISMATCH", "\u8BE6\u60C5\u9875\u6570\u636E\u4E0E\u8BF7\u6C42\u7684\u5E16\u5B50\u4E0D\u4E00\u81F4", "Error");
      }
      telemetry.complete("TARGET_IDENTITY_MATCHED");
      const authorValue = note.user;
      const authorObject = dataRecord(authorValue);
      telemetry.author_object_present = isRecordValue(authorValue);
      if (!telemetry.author_object_present) {
        telemetry.fail("AUTHOR_MISSING", "\u8BE6\u60C5\u9875\u6570\u636E\u4E0E\u8BF7\u6C42\u7684\u5E16\u5B50\u4E0D\u4E00\u81F4", "Error");
      }
      const authorId = dataText(authorObject.userId ?? authorObject.user_id);
      telemetry.author_id_present = Boolean(authorId);
      if (!telemetry.author_id_present) {
        telemetry.fail("AUTHOR_ID_MISSING", "\u8BE6\u60C5\u9875\u6570\u636E\u4E0E\u8BF7\u6C42\u7684\u5E16\u5B50\u4E0D\u4E00\u81F4", "Error");
      }
      const author = parseFeedAuthor(authorValue);
      if (!author) {
        telemetry.fail("AUTHOR_MISSING", "\u8BE6\u60C5\u9875\u6570\u636E\u4E0E\u8BF7\u6C42\u7684\u5E16\u5B50\u4E0D\u4E00\u81F4", "Error");
      }
      const parsedAuthor = author;
      telemetry.complete("AUTHOR_VALIDATED");
      const imageListValue = note.imageList;
      telemetry.image_list_present = Array.isArray(imageListValue);
      telemetry.image_list_length = Array.isArray(imageListValue) ? boundedCount(imageListValue.length) : 0;
      telemetry.normalized_note_type = normalizedNoteType(note.type);
      telemetry.complete("MEDIA_FIELDS_VALIDATED");
      const comments = dataRecord(unwrapState(locatedRecord.wrapper.comments));
      const detail = {
        feed_id: options.feedId,
        xsec_token: dataText(note.xsecToken) || options.xsecToken,
        title: dataText(note.title).slice(0, 500),
        body: dataText(note.desc).slice(0, 2e4),
        note_type: noteType2(note.type),
        author: parsedAuthor,
        metrics: parseFeedMetrics(note.interactInfo),
        image_urls: dataList(note.imageList).map((item) => {
          const image = dataRecord(item);
          const url = dataUrl(image.urlDefault ?? image.urlPre ?? image.url);
          return url ? normalizeFeedImageUrl(url) : null;
        }).filter((url) => url !== null).slice(0, 100),
        published_at: dataInteger(note.time),
        ip_location: dataText(note.ipLocation).slice(0, 200),
        comments: dataList(unwrapState(comments.list)).slice(0, options.commentLimit).map((item) => parseComment(item, options.includeReplies, options.replyLimit)).filter((item) => item !== null),
        comments_has_more: dataBoolean(comments.hasMore),
        comments_cursor: dataText(comments.cursor).slice(0, 2048)
      };
      telemetry.parser_failure_subtype = "NONE";
      telemetry.safe_exception_class = "NONE";
      telemetry.complete("PARSE_COMPLETE");
      return { detail, telemetry: telemetry.snapshot() };
    } catch (error) {
      if (error instanceof FeedDetailParserError) throw error;
      return telemetry.fail(
        "UNEXPECTED_PARSER_EXCEPTION",
        "\u8BE6\u60C5\u9875\u89E3\u6790\u5931\u8D25",
        exceptionClass(error)
      );
    }
  }
  function findDetail(detailMap, feedId) {
    const direct = dataRecord(detailMap[feedId]);
    if (Object.keys(direct).length) return { wrapper: direct, matchMode: "EXACT_KEY" };
    const match = Object.values(detailMap).map(dataRecord).find((item) => dataText(dataRecord(item.note).noteId) === feedId);
    if (!match) return void 0;
    return { wrapper: match, matchMode: "NOTE_ID_SCAN" };
  }
  function parseComment(value, includeReplies, replyLimit) {
    const comment = dataRecord(value);
    const author = parseFeedAuthor(comment.userInfo);
    const commentId2 = dataText(comment.id);
    if (!commentId2 || !author) return null;
    const replies = includeReplies ? dataList(unwrapState(comment.subComments)).slice(0, replyLimit).map((item) => parseComment(item, false, 0)).filter((item) => item !== null) : [];
    return {
      comment_id: commentId2,
      content: dataText(comment.content).slice(0, 5e3),
      author,
      liked: dataBoolean(comment.liked),
      like_count: dataText(comment.likeCount) || "0",
      created_at: dataInteger(comment.createTime),
      ip_location: dataText(comment.ipLocation).slice(0, 200),
      reply_count: dataText(comment.subCommentCount) || String(replies.length),
      replies
    };
  }
  function noteType2(value) {
    const type = dataText(value).toLowerCase();
    if (type === "video") return "video";
    if (type === "normal" || type === "image") return "image";
    return "unknown";
  }

  // src/feed-media-parser.ts
  var FeedMediaParserError = class extends Error {
    constructor(message, diagnostics) {
      super(message);
      this.diagnostics = diagnostics;
      this.name = "FeedMediaParserError";
    }
    diagnostics;
  };
  function feedMediaParserDiagnosticsFromError(error) {
    return error instanceof FeedMediaParserError ? error.diagnostics : void 0;
  }
  async function parseFeedMediaDocument(page, feedId, sourceUrl) {
    let stateInspection = emptyStateInspection();
    let stateRejection = "UNKNOWN";
    const scripts = [...page.scripts].map((script) => script.textContent?.trim() ?? "").filter((text3) => text3.startsWith("window.__INITIAL_STATE__")).reverse();
    for (const script of scripts) {
      try {
        const state = parseInitialStateValue(script);
        stateInspection = inspectInitialStateVideo(state, sourceUrl);
        stateRejection = stateRejectionFromInspection(stateInspection);
        const work = parseInitialStateScript(script, sourceUrl);
        if (work.workId !== feedId) throw new Error("\u5A92\u4F53\u7ED3\u679C\u4E0E\u8BF7\u6C42\u5E16\u5B50\u4E0D\u4E00\u81F4");
        const result = feedMediaResult(feedId, work.media);
        if (result.media.length) return result;
      } catch (error) {
        if (error instanceof Error && error.message.includes("\u4E0D\u4E00\u81F4")) throw error;
        stateRejection = "UNEXPECTED_MEDIA_SCHEMA";
      }
    }
    try {
      const state = await readLiveInitialState(page);
      stateInspection = inspectInitialStateVideo(state, sourceUrl);
      stateRejection = stateRejectionFromInspection(stateInspection);
      const work = parseInitialStateRecord(state, sourceUrl);
      if (work.workId !== feedId) throw new Error("\u5A92\u4F53\u7ED3\u679C\u4E0E\u8BF7\u6C42\u5E16\u5B50\u4E0D\u4E00\u81F4");
      const result = feedMediaResult(feedId, work.media);
      if (result.media.length) return result;
    } catch (error) {
      if (error instanceof Error && error.message.includes("\u4E0D\u4E00\u81F4")) throw error;
      stateRejection = stateRejection === "UNKNOWN" ? "UNEXPECTED_MEDIA_SCHEMA" : stateRejection;
    }
    const domCandidate = findDomVideoCandidate(page);
    if (domCandidate.result) {
      return {
        feed_id: feedId,
        note_type: "video",
        media: [
          {
            index: 1,
            kind: "video",
            url: domCandidate.result.url,
            suffix: "mp4"
          }
        ]
      };
    }
    throw new FeedMediaParserError(
      "\u9875\u9762\u6CA1\u6709\u8BF7\u6C42\u5E16\u5B50\u7684\u89C6\u9891\u5A92\u4F53",
      buildDiagnostics(page, stateInspection, stateRejection, domCandidate)
    );
  }
  function feedMediaResult(feedId, media) {
    return {
      feed_id: feedId,
      note_type: media.some((item) => item.kind === "video") ? "video" : "unknown",
      media
    };
  }
  function emptyStateInspection() {
    return {
      video_object_present: false,
      video_keys_class: "EMPTY",
      video_stream_object_present: false,
      video_variant_count: 0
    };
  }
  function stateRejectionFromInspection(inspection) {
    if (!inspection.video_object_present) return "NO_VIDEO_OBJECT";
    if (!inspection.video_stream_object_present) {
      return inspection.video_keys_class === "KNOWN_FIELDS" ? "KNOWN_FIELDS_EMPTY" : inspection.video_keys_class === "OTHER" ? "VIDEO_OBJECT_SCHEMA_UNSUPPORTED" : "STREAM_OBJECT_MISSING";
    }
    return inspection.video_variant_count ? "UNKNOWN" : "STREAM_VARIANTS_EMPTY";
  }
  function findDomVideoCandidate(page) {
    const videos = [...page.querySelectorAll("video")];
    const sources = [...page.querySelectorAll("video source")];
    const candidates = [];
    let videoSrcPresent = false;
    let videoCurrentSrcPresent = false;
    let sourceSrcPresent = false;
    for (const video of videos) {
      const currentSrc = video.currentSrc || "";
      const src = video.src || video.getAttribute("src") || "";
      if (currentSrc) {
        videoCurrentSrcPresent = true;
        candidates.push({ value: currentSrc, source: "VIDEO_ELEMENT_CURRENT_SRC" });
      }
      if (src) {
        videoSrcPresent = true;
        candidates.push({ value: src, source: "VIDEO_ELEMENT_SRC" });
      }
    }
    for (const source of sources) {
      const src = source.src || source.getAttribute("src") || "";
      if (src) {
        sourceSrcPresent = true;
        candidates.push({ value: src, source: "SOURCE_ELEMENT_SRC" });
      }
    }
    let latest = emptyLocatorAssessment("DOM_VIDEO_ELEMENT_MISSING");
    for (const candidate of candidates) {
      const assessment = assessVideoUrl(candidate.value);
      latest = { ...assessment, source: candidate.source };
      if (assessment.accepted) {
        return {
          result: { url: candidate.value, source: candidate.source },
          videoElementCount: videos.length,
          sourceElementCount: sources.length,
          videoSrcPresent,
          videoCurrentSrcPresent,
          sourceSrcPresent,
          hostClass: assessment.hostClass,
          pathClass: assessment.pathClass,
          signedQuery: assessment.signedQuery,
          rejection: "UNKNOWN"
        };
      }
    }
    const rejection = videos.length === 0 ? "DOM_VIDEO_ELEMENT_MISSING" : candidates.length === 0 ? sources.length ? "DOM_SOURCE_SRC_EMPTY" : "DOM_VIDEO_SRC_EMPTY" : latest.rejection;
    return {
      videoElementCount: videos.length,
      sourceElementCount: sources.length,
      videoSrcPresent,
      videoCurrentSrcPresent,
      sourceSrcPresent,
      hostClass: latest.hostClass,
      pathClass: latest.pathClass,
      signedQuery: latest.signedQuery,
      rejection
    };
  }
  function buildDiagnostics(page, state, stateRejection, dom) {
    return {
      video_element_count: dom.videoElementCount,
      source_element_count: dom.sourceElementCount,
      video_src_present: dom.videoSrcPresent ? "YES" : "NO",
      video_current_src_present: dom.videoCurrentSrcPresent ? "YES" : "NO",
      source_src_present: dom.sourceSrcPresent ? "YES" : "NO",
      initial_state_video_object_present: state.video_object_present ? "YES" : "NO",
      initial_state_video_keys_class: state.video_keys_class,
      video_stream_object_present: state.video_stream_object_present ? "YES" : "NO",
      video_variant_count: state.video_variant_count,
      locator_candidate_source: dom.result?.source ?? "NONE",
      url_host_class: dom.hostClass,
      url_path_shape_class: dom.pathClass,
      signed_query_present: dom.signedQuery,
      locator_rejection_reason: dom.videoElementCount > 0 || dom.sourceElementCount > 0 ? dom.rejection : stateRejection,
      page_has_initial_state_script: page.scripts.length > 0 ? "YES" : "NO"
    };
  }
  function emptyLocatorAssessment(rejection) {
    return {
      accepted: false,
      hostClass: "UNKNOWN",
      pathClass: "UNKNOWN",
      signedQuery: "NO",
      rejection,
      source: "NONE"
    };
  }
  function assessVideoUrl(value) {
    if (value.startsWith("blob:")) return emptyLocatorAssessment("BLOB_ONLY_SOURCE");
    let parsed;
    try {
      parsed = new URL(value);
    } catch {
      return emptyLocatorAssessment("CANDIDATE_REJECTED");
    }
    const hostClass = isXhsVideoHost(parsed.hostname) ? "XHS_MEDIA_HOST" : "OTHER";
    const pathClass = videoPathShape(parsed.pathname);
    const signedQuery = parsed.search ? "YES" : "NO";
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return { accepted: false, hostClass, pathClass, signedQuery, rejection: "CANDIDATE_REJECTED" };
    }
    if (hostClass !== "XHS_MEDIA_HOST" || !parsed.pathname || parsed.pathname === "/") {
      return { accepted: false, hostClass, pathClass, signedQuery, rejection: "CANDIDATE_REJECTED" };
    }
    return { accepted: true, hostClass, pathClass, signedQuery, rejection: "UNKNOWN" };
  }
  function isXhsVideoHost(hostname) {
    return /^sns-video-[a-z0-9-]+\.xhscdn\.(com|net)$/i.test(hostname);
  }
  function videoPathShape(pathname) {
    if (/\.(mp4|webm)(?:$|\/)/i.test(pathname)) return "VIDEO_FILE";
    if (/\.(m3u8|mpd)(?:$|\/)/i.test(pathname)) return "VIDEO_STREAM";
    if (pathname.includes("/video") || pathname.includes("/stream")) return "XHS_VIDEO_PATH";
    return "UNKNOWN";
  }

  // src/interaction-runner.ts
  var SELECTORS = {
    like: ".interact-container .left .like-lottie",
    favorite: ".interact-container .left .reds-icon.collect-icon"
  };
  var CONTROL_READY_ATTEMPTS = 20;
  var CONTROL_READY_INTERVAL_MS = 250;
  async function setDesiredInteraction(page, feedId, kind, active, activate) {
    const preparation = await prepareDesiredInteraction(page, feedId, kind, active);
    if (preparation.result) return preparation.result;
    if (activate) await activate();
    else clickInteractionControl(page, preparation.selector);
    return verifyDesiredInteraction(page, feedId, kind, active);
  }
  async function prepareDesiredInteraction(page, feedId, kind, active) {
    const before = interactionState(await readLiveInitialState(page), feedId, kind);
    if (before === active) {
      return {
        result: {
          feed_id: feedId,
          kind,
          active,
          changed: false,
          verified: true
        },
        selector: null
      };
    }
    const control = await waitForInteractionControl(page, kind);
    if (!control) {
      throw new Error(kind === "like" ? "\u9875\u9762\u6CA1\u6709\u70B9\u8D5E\u6309\u94AE" : "\u9875\u9762\u6CA1\u6709\u6536\u85CF\u6309\u94AE");
    }
    return { result: null, selector: SELECTORS[kind] };
  }
  async function verifyDesiredInteraction(page, feedId, kind, active) {
    for (let attempt = 0; attempt < 16; attempt += 1) {
      try {
        const current = interactionState(await readLiveInitialState(page), feedId, kind);
        if (current === active) {
          return {
            feed_id: feedId,
            kind,
            active,
            changed: true,
            verified: true
          };
        }
      } catch {
      }
      await delay4(250);
    }
    const action = kind === "like" ? "\u70B9\u8D5E" : "\u6536\u85CF";
    throw new UncertainBrowserActionError(`${action}\u64CD\u4F5C\u5DF2\u89E6\u53D1\uFF0C\u4F46\u672A\u80FD\u786E\u8BA4\u6700\u7EC8\u72B6\u6001\uFF0C\u8BF7\u4EBA\u5DE5\u6838\u5BF9`);
  }
  async function waitForInteractionControl(page, kind) {
    for (let attempt = 0; attempt < CONTROL_READY_ATTEMPTS; attempt += 1) {
      const control = page.querySelector(SELECTORS[kind]);
      if (control) return control;
      await delay4(CONTROL_READY_INTERVAL_MS);
    }
    return null;
  }
  function clickInteractionControl(page, selector) {
    const control = page.querySelector(selector);
    if (!control) throw new Error("\u4E92\u52A8\u6309\u94AE\u5728\u6267\u884C\u524D\u5DF2\u7ECF\u5931\u6548");
    const clickable = control;
    if (typeof clickable.click === "function") {
      clickable.click();
      return;
    }
    const MouseEventConstructor = page.defaultView?.MouseEvent;
    if (!MouseEventConstructor) {
      throw new Error("\u5F53\u524D\u9875\u9762\u65E0\u6CD5\u89E6\u53D1\u4E92\u52A8\u6309\u94AE");
    }
    control.dispatchEvent(
      new MouseEventConstructor("click", {
        bubbles: true,
        cancelable: true,
        composed: true
      })
    );
  }
  function interactionState(state, feedId, kind) {
    const note = dataRecord(state.note);
    const detailMap = dataRecord(note.noteDetailMap);
    const direct = dataRecord(detailMap[feedId]);
    const wrapper = (Object.keys(direct).length ? direct : null) ?? Object.values(detailMap).map(dataRecord).find((item) => dataText(dataRecord(item.note).noteId) === feedId);
    const interact = dataRecord(dataRecord(wrapper).note);
    const info = dataRecord(interact.interactInfo);
    const field = kind === "like" ? "liked" : "collected";
    if (typeof info[field] !== "boolean") {
      throw new Error("\u9875\u9762\u6CA1\u6709\u53EF\u6838\u9A8C\u7684\u4E92\u52A8\u72B6\u6001");
    }
    if (dataText(interact.noteId) !== feedId) {
      throw new Error("\u9875\u9762\u4E92\u52A8\u72B6\u6001\u4E0D\u5C5E\u4E8E\u76EE\u6807\u5E16\u5B50");
    }
    return info[field];
  }
  function delay4(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/profile-parser.ts
  function parseUserProfileDocument(page, requestedUserId, currentState) {
    const state = currentState ?? latestInitialState(page);
    const userState = dataRecord(state.user);
    const pageData = dataRecord(unwrapState(userState.userPageData));
    const basic = dataRecord(pageData.basicInfo);
    if (!Object.keys(basic).length) throw new Error("\u7528\u6237\u4E3B\u9875\u8D44\u6599\u5C1A\u672A\u52A0\u8F7D");
    const feeds = parseFeedSummaries(unwrapState(userState.notes));
    return {
      user_id: dataText(basic.userId ?? basic.user_id) || requestedUserId || null,
      nickname: dataText(basic.nickname).slice(0, 200),
      red_id: dataText(basic.redId).slice(0, 200),
      description: dataText(basic.desc).slice(0, 5e3),
      avatar_url: dataUrl(basic.imageb ?? basic.images),
      ip_location: dataText(basic.ipLocation).slice(0, 200),
      metrics: dataList(pageData.interactions).map(parseMetric).filter((item) => item !== null),
      feeds: feeds.slice(0, 500)
    };
  }
  function parseMetric(value) {
    const metric = dataRecord(value);
    const name = dataText(metric.name);
    if (!name) return null;
    return {
      name: name.slice(0, 100),
      count: (dataText(metric.count) || "0").slice(0, 100),
      metric_type: dataText(metric.type).slice(0, 100)
    };
  }

  // src/search-filters.ts
  var DEFAULT_FILTERS = {
    sort_by: "\u7EFC\u5408",
    note_type: "\u4E0D\u9650",
    publish_time: "\u4E0D\u9650",
    search_scope: "\u4E0D\u9650",
    location: "\u4E0D\u9650"
  };
  var FILTER_GROUPS = ["sort_by", "note_type", "publish_time", "search_scope", "location"];
  function hasCustomSearchFilters(filters) {
    return FILTER_GROUPS.some(
      (field) => typeof filters[field] === "string" && filters[field] !== DEFAULT_FILTERS[field]
    );
  }
  async function applySearchFilters(page, filters) {
    const triggerCandidate = page.querySelector(".filter") ?? findExactTextElement(page, "\u7B5B\u9009");
    const trigger = triggerCandidate?.closest("button, [role='button'], div.filter, div") ?? triggerCandidate;
    if (!trigger) throw new Error("\u641C\u7D22\u9875\u6CA1\u6709\u7B5B\u9009\u5165\u53E3");
    trigger.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
    trigger.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    const scope = await waitForFilterOptions(page);
    for (const field of FILTER_GROUPS) {
      const wanted = filters[field];
      if (typeof wanted !== "string" || wanted === DEFAULT_FILTERS[field]) continue;
      const target = [...scope.querySelectorAll("div.tags")].find(
        (item) => item.textContent?.trim() === wanted
      ) ?? findExactTextElement(scope, wanted);
      if (!target) throw new Error(`\u641C\u7D22\u9875\u6CA1\u6709\u7B5B\u9009\u9009\u9879 ${wanted}`);
      target.click();
      await delay5(150);
    }
    await delay5(350);
  }
  async function waitForFilterOptions(page) {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const panel = page.querySelector(".filter-panel");
      if (panel) return panel;
      if (findExactTextElement(page, "\u6700\u65B0")) return page;
      await delay5(100);
    }
    throw new Error("\u641C\u7D22\u7B5B\u9009\u9762\u677F\u672A\u80FD\u53CA\u65F6\u6253\u5F00");
  }
  function findExactTextElement(scope, text3) {
    const candidates = scope.querySelectorAll("button, [role='button'], div, span");
    return [...candidates].find(
      (element) => element.textContent?.trim() === text3 && ![...element.children].some((child) => child.textContent?.trim() === text3)
    ) ?? null;
  }
  function delay5(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/browser-runtime-telemetry.ts
  function attachPageRuntimeTelemetry(error, telemetry) {
    if (!error || typeof error !== "object") return;
    error.page_runtime_telemetry = telemetry;
  }

  // src/browser-page-runner.ts
  var SEARCH_READY_ATTEMPTS = 20;
  var SEARCH_READY_INTERVAL_MS = 250;
  async function executeBrowserPageTask(task, page, pageUrl, actions = {}) {
    if (task.kind === "check_login_status") {
      const state = detectLoginState(page, pageUrl);
      return {
        ok: true,
        message: state.logged_in ? "\u6D4F\u89C8\u5668\u5DF2\u767B\u5F55\u5C0F\u7EA2\u4E66" : "\u6D4F\u89C8\u5668\u5C1A\u672A\u767B\u5F55\u5C0F\u7EA2\u4E66",
        result: { ...state }
      };
    }
    if (task.kind === "get_login_qrcode") {
      const result = await waitForLoginQrCode(page, pageUrl);
      return success(
        result.is_logged_in ? "\u6D4F\u89C8\u5668\u5DF2\u767B\u5F55\uFF0C\u65E0\u9700\u518D\u6B21\u626B\u7801" : "\u767B\u5F55\u4E8C\u7EF4\u7801\u5DF2\u751F\u6210\uFF0C\u767B\u5F55\u9875\u9762\u5C06\u4FDD\u6301\u6253\u5F00",
        result
      );
    }
    if (task.kind === "list_feeds") {
      return success("\u63A8\u8350\u6D41\u8BFB\u53D6\u5B8C\u6210", parseFeedListDocument(page, "home"));
    }
    if (task.kind === "search_feeds") {
      const keyword = payloadText(task, "keyword");
      const filters = payloadRecord(task, "filters");
      if (hasCustomSearchFilters(filters)) {
        await applySearchFilters(page, filters);
      }
      return success("\u641C\u7D22\u7ED3\u679C\u8BFB\u53D6\u5B8C\u6210", await waitForSearchResult(page, keyword));
    }
    if (task.kind === "get_feed_detail") {
      const options = {
        feedId: payloadText(task, "feed_id"),
        xsecToken: payloadText(task, "xsec_token"),
        commentLimit: payloadNumber(task, "comment_limit"),
        includeReplies: task.payload.include_replies === true,
        replyLimit: payloadNumber(task, "reply_limit")
      };
      let currentState;
      if (needsCommentLoading(options)) {
        await loadComments(page, options);
        currentState = await readLiveInitialState(page);
      }
      const pageTelemetry = {
        content_script_message_received: false,
        page_task_started: true,
        parser_invocation_started: true
      };
      try {
        return {
          ...success(
            "\u5E16\u5B50\u8BE6\u60C5\u8BFB\u53D6\u5B8C\u6210",
            parseFeedDetailDocumentWithTelemetry(page, options, currentState).detail
          ),
          page_runtime_telemetry: pageTelemetry
        };
      } catch (error) {
        attachPageRuntimeTelemetry(error, pageTelemetry);
        throw error;
      }
    }
    if (task.kind === "get_feed_media") {
      const feedId = payloadText(task, "feed_id");
      return success(
        "\u5E16\u5B50\u89C6\u9891\u5A92\u4F53\u8BFB\u53D6\u5B8C\u6210",
        await parseFeedMediaDocument(page, feedId, pageUrl)
      );
    }
    if (task.kind === "get_user_profile") {
      return success(
        "\u7528\u6237\u4E3B\u9875\u8BFB\u53D6\u5B8C\u6210",
        parseUserProfileDocument(page, payloadText(task, "user_id"))
      );
    }
    if (task.kind === "get_my_profile") {
      if (new URL(pageUrl).pathname.includes("/user/profile/")) {
        return success(
          "\u5F53\u524D\u8D26\u53F7\u4E3B\u9875\u8BFB\u53D6\u5B8C\u6210",
          parseUserProfileDocument(page, profileUserId(pageUrl))
        );
      }
      const profileLink = page.querySelector(
        '.main-container .user a[href*="/user/profile/"]'
      );
      if (profileLink?.href) {
        profileLink.click();
        return {
          ok: false,
          message: "\u6B63\u5728\u6253\u5F00\u5F53\u524D\u8D26\u53F7\u4E3B\u9875",
          navigateUrl: profileLink.href
        };
      }
      throw new Error("\u5F53\u524D\u9875\u9762\u6CA1\u6709\u5DF2\u767B\u5F55\u8D26\u53F7\u7684\u4E3B\u9875\u5165\u53E3");
    }
    if (task.kind === "set_like" || task.kind === "set_favorite") {
      const active = payloadBoolean(task, "active");
      return success(
        active ? "\u4E92\u52A8\u72B6\u6001\u5DF2\u542F\u7528" : "\u4E92\u52A8\u72B6\u6001\u5DF2\u53D6\u6D88",
        await setDesiredInteraction(
          page,
          payloadText(task, "feed_id"),
          task.kind === "set_like" ? "like" : "favorite",
          active,
          actions.activateInteraction ? () => actions.activateInteraction?.(
            task.task_id,
            task.kind === "set_like" ? "like" : "favorite"
          ) ?? Promise.resolve() : void 0
        )
      );
    }
    if (task.kind === "post_comment") {
      return success(
        "\u8BC4\u8BBA\u5DF2\u63D0\u4EA4\u5E76\u786E\u8BA4",
        await postComment(page, payloadText(task, "feed_id"), payloadText(task, "content"))
      );
    }
    if (task.kind === "reply_comment") {
      return success(
        "\u56DE\u590D\u5DF2\u63D0\u4EA4\u5E76\u786E\u8BA4",
        await replyComment(page, payloadText(task, "feed_id"), payloadText(task, "content"), {
          commentId: payloadOptionalText(task, "comment_id"),
          userId: payloadOptionalText(task, "user_id")
        })
      );
    }
    return {
      ok: false,
      message: `\u5F53\u524D\u6269\u5C55\u7248\u672C\u5C1A\u4E0D\u652F\u6301\u4EFB\u52A1 ${task.kind}`,
      result: buildPageCompatibilityDiagnostics(page, pageUrl)
    };
  }
  function success(message, result) {
    return {
      ok: true,
      message,
      result
    };
  }
  async function waitForSearchResult(page, keyword) {
    try {
      const initial = parseFeedListDocument(page, "search", keyword);
      if (initial.items.length) return initial;
    } catch {
    }
    let latest = {};
    for (let attempt = 0; attempt < SEARCH_READY_ATTEMPTS; attempt += 1) {
      latest = await readLiveInitialState(page);
      try {
        const result = parseFeedListDocument(page, "search", keyword, latest);
        if (result.items.length) return result;
      } catch {
      }
      await delay6(SEARCH_READY_INTERVAL_MS);
    }
    return parseFeedListDocument(page, "search", keyword, latest);
  }
  function payloadText(task, field) {
    const value = task.payload[field];
    if (typeof value !== "string" || !value) {
      throw new Error(`\u6D4F\u89C8\u5668\u4EFB\u52A1\u7F3A\u5C11\u53C2\u6570 ${field}`);
    }
    return value;
  }
  function payloadRecord(task, field) {
    const value = task.payload[field];
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }
  function payloadNumber(task, field) {
    const value = task.payload[field];
    if (typeof value !== "number" || !Number.isInteger(value)) {
      throw new Error(`\u6D4F\u89C8\u5668\u4EFB\u52A1\u53C2\u6570 ${field} \u65E0\u6548`);
    }
    return value;
  }
  function payloadBoolean(task, field) {
    const value = task.payload[field];
    if (typeof value !== "boolean") {
      throw new Error(`\u6D4F\u89C8\u5668\u4EFB\u52A1\u53C2\u6570 ${field} \u65E0\u6548`);
    }
    return value;
  }
  function payloadOptionalText(task, field) {
    const value = task.payload[field];
    return typeof value === "string" && value ? value : null;
  }
  function profileUserId(pageUrl) {
    const parts = new URL(pageUrl).pathname.split("/").filter(Boolean);
    if (parts[0] !== "user" || parts[1] !== "profile" || !parts[2]) return null;
    return decodeURIComponent(parts[2]);
  }
  function delay6(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  // src/browser-state-main.ts
  function installBrowserStateBridge(scope = window) {
    const events = browserStateEvents();
    const onRequest = (event) => {
      const requestId = requestIdFromDetail(event.detail);
      if (!requestId) return;
      try {
        const data = stringifyPageState(scope.__INITIAL_STATE__);
        if (!data) throw new Error("\u5C0F\u7EA2\u4E66\u5B9E\u65F6\u72B6\u6001\u5C1A\u672A\u52A0\u8F7D");
        respond(scope, events.response, { requestId, ok: true, data });
      } catch (error) {
        respond(scope, events.response, {
          requestId,
          ok: false,
          message: error instanceof Error ? error.message : "\u5B9E\u65F6\u72B6\u6001\u8BFB\u53D6\u5931\u8D25"
        });
      }
    };
    scope.addEventListener(events.request, onRequest);
    return () => scope.removeEventListener(events.request, onRequest);
  }
  function stringifyPageState(value) {
    const ancestors = [];
    return JSON.stringify(value, function(key, current) {
      if (isVueInternalField(key)) return void 0;
      if (!current || typeof current !== "object") return current;
      while (ancestors.length && ancestors.at(-1) !== this) ancestors.pop();
      if (ancestors.includes(current)) return void 0;
      ancestors.push(current);
      return current;
    });
  }
  function isVueInternalField(key) {
    return key.startsWith("__v_") || key === "dep" || key === "effect";
  }
  function requestIdFromDetail(value) {
    if (typeof value !== "string") return "";
    try {
      const parsed = JSON.parse(value);
      return typeof parsed.requestId === "string" ? parsed.requestId : "";
    } catch {
      return "";
    }
  }
  function respond(scope, eventName, value) {
    scope.dispatchEvent(new CustomEvent(eventName, { detail: JSON.stringify(value) }));
  }

  // src/managed-page-adapter.ts
  var MANAGED_PAGE_ADAPTER_GLOBAL = "__XHS_DOWNLOADER_MANAGED_PAGE_ADAPTER__";
  var MANAGED_PAGE_ADAPTER_VERSION = "3";
  var MANAGED_ADAPTER_GENERATION = "v2";
  var MANAGED_DIAGNOSTIC_SCHEMA_VERSION = "MANAGED-2";
  var MANAGED_RUNTIME_IDENTITY = {
    managed_adapter_generation: MANAGED_ADAPTER_GENERATION,
    diagnostic_schema_version: MANAGED_DIAGNOSTIC_SCHEMA_VERSION
  };
  function installManagedPageAdapter(scope = window) {
    const current = scope.__XHS_DOWNLOADER_MANAGED_PAGE_ADAPTER__;
    if (current?.version === MANAGED_PAGE_ADAPTER_VERSION && current.generation === MANAGED_ADAPTER_GENERATION) {
      return current;
    }
    installBrowserStateBridge(scope);
    const adapter = {
      version: MANAGED_PAGE_ADAPTER_VERSION,
      generation: MANAGED_ADAPTER_GENERATION,
      proveAccount: (challenge) => proveBrowserAccount(scope.document, challenge),
      execute: (task) => executeSafely(task, scope),
      prepareInteraction: (task) => prepareInteractionSafely(task, scope),
      verifyInteraction: (task) => verifyInteractionSafely(task, scope),
      diagnostics: () => ({
        ...MANAGED_RUNTIME_IDENTITY,
        ...buildPageCompatibilityDiagnostics(scope.document, scope.location.href)
      })
    };
    Object.defineProperty(scope, MANAGED_PAGE_ADAPTER_GLOBAL, {
      configurable: true,
      enumerable: false,
      value: adapter,
      writable: false
    });
    return adapter;
  }
  async function executeSafely(task, scope) {
    if (isInteractionTask(task)) {
      return failure(new Error("\u53D7\u7BA1\u6D4F\u89C8\u5668\u4E92\u52A8\u5FC5\u987B\u901A\u8FC7\u53EF\u4FE1\u8F93\u5165\u6D41\u7A0B\u6267\u884C"), scope);
    }
    try {
      return {
        ...await executeBrowserPageTask(task, scope.document, scope.location.href),
        managed_runtime_identity: MANAGED_RUNTIME_IDENTITY
      };
    } catch (error) {
      return failure(error, scope);
    }
  }
  async function prepareInteractionSafely(task, scope) {
    try {
      const input = interactionInput(task);
      const preparation = await prepareDesiredInteraction(
        scope.document,
        input.feedId,
        input.kind,
        input.active
      );
      if (preparation.result) {
        return success2("\u4E92\u52A8\u72B6\u6001\u5DF2\u7ECF\u6EE1\u8DB3\u76EE\u6807", preparation.result);
      }
      return {
        ok: false,
        message: "\u4E92\u52A8\u72B6\u6001\u9700\u8981\u53D7\u7BA1\u6D4F\u89C8\u5668\u53EF\u4FE1\u8F93\u5165",
        action: {
          task_id: task.task_id,
          feed_id: input.feedId,
          kind: input.kind,
          active: input.active,
          selector: preparation.selector
        }
      };
    } catch (error) {
      return failure(error, scope);
    }
  }
  async function verifyInteractionSafely(task, scope) {
    try {
      const input = interactionInput(task);
      return success2(
        "\u4E92\u52A8\u72B6\u6001\u5DF2\u901A\u8FC7\u9875\u9762\u5B9E\u65F6\u6570\u636E\u786E\u8BA4",
        await verifyDesiredInteraction(scope.document, input.feedId, input.kind, input.active)
      );
    } catch (error) {
      return failure(error, scope);
    }
  }
  function interactionInput(task) {
    if (!isInteractionTask(task)) {
      throw new Error("\u5F53\u524D\u4EFB\u52A1\u4E0D\u662F\u53D7\u652F\u6301\u7684\u4E92\u52A8\u7C7B\u578B");
    }
    const feedId = task.payload.feed_id;
    const active = task.payload.active;
    if (typeof feedId !== "string" || !feedId) {
      throw new Error("\u6D4F\u89C8\u5668\u4EFB\u52A1\u7F3A\u5C11\u53C2\u6570 feed_id");
    }
    if (typeof active !== "boolean") {
      throw new Error("\u6D4F\u89C8\u5668\u4EFB\u52A1\u53C2\u6570 active \u65E0\u6548");
    }
    return {
      feedId,
      kind: task.kind === "set_like" ? "like" : "favorite",
      active
    };
  }
  function isInteractionTask(task) {
    return task.kind === "set_like" || task.kind === "set_favorite";
  }
  function success2(message, result) {
    return {
      ok: true,
      message,
      result
    };
  }
  function failure(error, scope) {
    const mediaParserDiagnostics = feedMediaParserDiagnosticsFromError(error);
    return {
      ok: false,
      message: error instanceof Error ? error.message : "\u9875\u9762\u6570\u636E\u89E3\u6790\u5931\u8D25",
      status: error instanceof UncertainBrowserActionError ? "needs_review" : "failed",
      result: {
        ...MANAGED_RUNTIME_IDENTITY,
        ...buildPageCompatibilityDiagnostics(scope.document, scope.location.href),
        ...mediaParserDiagnostics ? { media_parser_diagnostics: mediaParserDiagnostics } : {}
      }
    };
  }
  installManagedPageAdapter();
})();
