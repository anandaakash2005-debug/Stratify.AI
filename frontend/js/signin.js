import { supabase } from './supabase.js'

/* ============================================
   SIGNIN.JS — Sign In Page Logic
   Satquery.AI — Startup Intelligence
   ============================================ */

/* ---- State ---- */
const SignIn = {
  isLoading: false,
  passwordVisible: false,
};

/* ---- DOM refs (populated on DOMContentLoaded) ---- */
let $form, $emailInput, $passwordInput, $rememberChk,
    $submitBtn, $pwToggle,
    $emailMsg, $passwordMsg;

/* ============================================
   VALIDATION HELPERS
   ============================================ */

/** Email regex */
function isValidEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
}

/** Min 8 chars */
function isValidPassword(v) {
  return v.length >= 8;
}

/**
 * Set field state: idle | success | error
 */
function setFieldState(input, msgEl, state, message = '') {
  input.classList.remove('is-valid', 'is-invalid', 'error');
  msgEl.textContent = '';
  msgEl.className = 'field-message';

  if (state === 'success') {
    input.classList.add('is-valid');
    msgEl.classList.add('success');
    msgEl.textContent = message;
  } else if (state === 'error') {
    input.classList.add('is-invalid', 'error');
    msgEl.classList.add('error');
    msgEl.textContent = message;
  }
}

/**
 * Validate email field live
 */
function validateEmail(showSuccess = false) {
  const val = $emailInput.value;
  if (!val) {
    setFieldState($emailInput, $emailMsg, 'idle');
    return false;
  }
  if (!isValidEmail(val)) {
    setFieldState($emailInput, $emailMsg, 'error', '⚠ Enter a valid email address');
    return false;
  }
  if (showSuccess) {
    setFieldState($emailInput, $emailMsg, 'success', '✓ Looks good');
  } else {
    setFieldState($emailInput, $emailMsg, 'idle');
  }
  return true;
}

/**
 * Validate password field live
 */
function validatePassword(showSuccess = false) {
  const val = $passwordInput.value;
  if (!val) {
    setFieldState($passwordInput, $passwordMsg, 'idle');
    return false;
  }
  if (!isValidPassword(val)) {
    setFieldState($passwordInput, $passwordMsg, 'error', '⚠ Minimum 8 characters required');
    return false;
  }
  if (showSuccess) {
    setFieldState($passwordInput, $passwordMsg, 'success', '✓ Strong password');
  } else {
    setFieldState($passwordInput, $passwordMsg, 'idle');
  }
  return true;
}

/**
 * Run full validation before submit
 */
function validateAll() {
  const emailOk = validateEmail(true);
  const passOk  = validatePassword(true);
  return emailOk && passOk;
}

/* ============================================
   PASSWORD TOGGLE
   ============================================ */
function togglePassword() {
  SignIn.passwordVisible = !SignIn.passwordVisible;
  $passwordInput.type = SignIn.passwordVisible ? 'text' : 'password';
  $pwToggle.textContent = SignIn.passwordVisible ? '🙈' : '👁';
  $pwToggle.setAttribute('aria-label', SignIn.passwordVisible ? 'Hide password' : 'Show password');
}

/* ============================================
   SUBMIT BUTTON STATE
   ============================================ */
function setLoading(on) {
  SignIn.isLoading = on;
  $submitBtn.classList.toggle('loading', on);
  $submitBtn.disabled = on;
}

/* ============================================
   SUPABASE SIGNIN FLOW
   ============================================ */

async function signInWithSupabase(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    throw error;
  }

  return {
    user: data.user,
    session: data.session,
  };
}

/**
 * Handle form submission
 */
async function handleSignIn(e) {
  e.preventDefault();
  if (SignIn.isLoading) return;

  /* Validate */
  if (!validateAll()) {
    Toast.warning('Check your inputs', 'Please fix the highlighted fields before signing in.');
    return;
  }

  const email    = $emailInput.value.trim();
  const password = $passwordInput.value;
  const remember = $rememberChk.checked;

  setLoading(true);

  try {
    const result = await signInWithSupabase(email, password);

    const authPayload = {
      user: result.user,
      token: result.session?.access_token || null,
    };

    Auth.storeAuth(authPayload, remember);
    Auth.updateNavbarAuth();

    const user = result.user;
    const userName = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.name || user?.email?.split('@')[0] || 'User';

    /* Success toast */
    Toast.success(
      `Welcome back, ${userName.split(' ')[0]}!`,
      'Redirecting to your dashboard…',
      3000
    );

    /* Success visual state on form */
    $submitBtn.textContent = '✓ Signed In';
    $submitBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';

    /* Redirect after short delay */
    setTimeout(() => {
      window.location.href = getRedirectTarget('index.html');
    }, 1400);

  } catch (err) {
    setLoading(false);

    /* Shake animation on card */
    const card = document.querySelector('.auth-card');
    card.style.animation = 'none';
    requestAnimationFrame(() => {
      card.style.animation = 'cardShake 0.45s ease';
    });

    Toast.error('Sign In Failed', err.message || 'Something went wrong. Please try again.');

    /* Error state on fields */
    setFieldState($emailInput,    $emailMsg,    'error', '');
    setFieldState($passwordInput, $passwordMsg, 'error', '⚠ ' + err.message);
  }
}

/* ============================================
   OAUTH BUTTONS (demo stubs)
   ============================================ */
function handleGoogleSignIn() {
  Toast.info('Google Sign In', 'OAuth flow would launch here in production.', 3000);
}

function handleGithubSignIn() {
  Toast.info('GitHub Sign In', 'OAuth flow would launch here in production.', 3000);
}

/* ============================================
   PROGRESS BAR ANIMATION (on visual panel)
   ============================================ */
function animateVisualPanel() {
  /* Animate progress bars in the preview card */
  const bars = document.querySelectorAll('.visual-panel .progress-fill[data-width]');
  setTimeout(() => {
    bars.forEach((bar, i) => {
      setTimeout(() => {
        bar.style.width = bar.dataset.width + '%';
      }, i * 200);
    });
  }, 600);

  /* Animate the score arc SVG */
  const arc = document.querySelector('.score-arc');
  if (arc) {
    setTimeout(() => {
      arc.style.strokeDashoffset = '55'; /* 220 - (220 * 75/100) */
    }, 800);
  }
}

/* ============================================
   FOCUS EFFECTS — Glow on active input
   ============================================ */
function initInputGlows() {
  document.querySelectorAll('.input-wrap .form-control').forEach(input => {
    const wrap = input.closest('.input-wrap');

    input.addEventListener('focus', () => {
      wrap.style.filter = 'drop-shadow(0 0 8px rgba(99,102,241,0.25))';
    });

    input.addEventListener('blur', () => {
      wrap.style.filter = '';
    });
  });
}

/* ============================================
   CARD SHAKE KEYFRAME (injected dynamically)
   ============================================ */
function injectShakeKeyframe() {
  if (document.querySelector('#shake-style')) return;
  const style = document.createElement('style');
  style.id = 'shake-style';
  style.textContent = `
    @keyframes cardShake {
      0%,100% { transform: translateX(0); }
      15%      { transform: translateX(-8px); }
      30%      { transform: translateX(8px); }
      45%      { transform: translateX(-6px); }
      60%      { transform: translateX(6px); }
      75%      { transform: translateX(-3px); }
      90%      { transform: translateX(3px); }
    }
  `;
  document.head.appendChild(style);
}

/* ============================================
   LIVE COUNTER ANIMATION (floating cards)
   ============================================ */
function animateFloatCounters() {
  /* Survival Score counter */
  const scoreEl = document.querySelector('.score-ring-value[data-count]');
  if (scoreEl) {
    const target = parseInt(scoreEl.dataset.count, 10);
    animateCounter(scoreEl, target, 1600, '');
  }
}

/* ============================================
   KEYBOARD SHORTCUTS
   ============================================ */
function getRedirectTarget(defaultTarget = 'index.html') {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get('redirect');
  if (!redirect) return defaultTarget;
  return redirect;
}

function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    /* Ctrl/Cmd + Enter submits */
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      $form.requestSubmit();
    }
  });
}

/* ============================================
   AUTO-FILL VISUAL DEMO (for demo mode only)
   ============================================ */
function initDemoMode() {
  const demoBtn = document.getElementById('demo-signin');
  if (!demoBtn) return;

  demoBtn.addEventListener('click', () => {
    $emailInput.value    = 'founder@mystartup.io';
    $passwordInput.value = 'demo1234';
    $rememberChk.checked = true;

    /* Trigger validation visuals */
    $emailInput.dispatchEvent(new Event('blur'));
    $passwordInput.dispatchEvent(new Event('blur'));

    Toast.info('Demo mode', 'Fields pre-filled with demo credentials. Click Sign In.', 3000);
  });
}

/* ============================================
   INIT
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
  /* Cache DOM */
  $form         = document.getElementById('signin-form');
  $emailInput   = document.getElementById('email');
  $passwordInput= document.getElementById('password');
  $rememberChk  = document.getElementById('remember');
  $submitBtn    = document.getElementById('signin-btn');
  $pwToggle     = document.getElementById('pw-toggle');
  $emailMsg     = document.getElementById('email-msg');
  $passwordMsg  = document.getElementById('password-msg');

  if (!$form) return; /* Safety guard */

  /* Inject shake keyframe */
  injectShakeKeyframe();

  /* Form events */
  $form.addEventListener('submit', handleSignIn);

  /* Live validation on blur */
  $emailInput.addEventListener('blur', () => validateEmail(false));
  $passwordInput.addEventListener('blur', () => validatePassword(false));

  /* Live validation on input (after first blur) */
  let emailTouched = false, passTouched = false;
  $emailInput.addEventListener('focus', () => { emailTouched = true; });
  $emailInput.addEventListener('input', () => { if (emailTouched) validateEmail(false); });
  $passwordInput.addEventListener('focus', () => { passTouched = true; });
  $passwordInput.addEventListener('input', () => { if (passTouched) validatePassword(false); });

  /* Password toggle */
  if ($pwToggle) {
    $pwToggle.addEventListener('click', togglePassword);
  }

  /* OAuth stubs */
  const googleBtn = document.getElementById('btn-google');
  const githubBtn = document.getElementById('btn-github');
  if (googleBtn) googleBtn.addEventListener('click', handleGoogleSignIn);
  if (githubBtn) githubBtn.addEventListener('click', handleGithubSignIn);

  /* Visual panel */
  animateVisualPanel();
  animateFloatCounters();

  /* Input glows */
  initInputGlows();

  /* Keyboard shortcuts */
  initKeyboardShortcuts();

  /* Demo mode */
  initDemoMode();

  /* Stagger card entry animation */
  const card = document.querySelector('.auth-card');
  if (card) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(24px)';
    requestAnimationFrame(() => {
      setTimeout(() => {
        card.style.transition = 'opacity 0.6s cubic-bezier(0.16,1,0.3,1), transform 0.6s cubic-bezier(0.16,1,0.3,1)';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      }, 100);
    });
  }
});