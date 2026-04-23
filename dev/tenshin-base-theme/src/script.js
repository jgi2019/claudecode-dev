/**
 * 点心 丹波篠山 — HEROパララックス
 * 対象：.parallax-target（HERO背景写真）のみ
 * 適用条件：PC（>768px）かつ prefers-reduced-motion: no-preference
 */
(function () {
  'use strict';

  // 実機で重く感じたら 0.3 に下げる
  const PARALLAX_RATIO = 0.4;
  const MOBILE_BREAKPOINT = 768;

  if (window.innerWidth <= MOBILE_BREAKPOINT) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const target = document.querySelector('.parallax-target');
  if (!target) return;

  let scrollY = 0;
  let ticking = false;

  function update() {
    // 画像を上方向に動かす（スクロール量 × 係数）
    target.style.transform = 'translate3d(0, ' + (-scrollY * PARALLAX_RATIO) + 'px, 0)';
    ticking = false;
  }

  function onScroll() {
    scrollY = window.scrollY;
    if (!ticking) {
      window.requestAnimationFrame(update);
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
})();
