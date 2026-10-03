import { supabase } from './supabase.js'
/* ============================================
   SIGNUP.JS — Sign Up Page Logic
   Satquery.AI — Startup Intelligence
   ============================================ */

/* ---- Page State ---- */
const SignUp = {
  isLoading:        false,
  passwordVisible:  false,
  confirmVisible:   false,
  strengthScore:    0,
  fieldsTouched:    { name: false, email: false, password: false, confirm: false },
};

/* ---- DOM Refs (cached on DOMContentLoaded) ---- */
let $form, $nameInput, $emailInput, $passwordInput, $confirmInput,
    $termsChk, $submitBtn,
    $pwToggle, $confirmToggle,
    $nameMsg, $emailMsg, $passwordMsg, $confirmMsg,
    $strengthWrap, $strengthBars, $strengthLabelText, $strengthHints,
    $successOverlay;

/* ============================================
   VALIDATION HELPERS
   ============================================ */

function isValidName(v)     { return v.trim().length >= 2; }
function isValidEmail(v)    { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()); }
function isValidPassword(v) { return v.length >= 8; }
function passwordsMatch(a, b){ return a === b && a.length > 0; }

/**
 * Apply valid/invalid class and render field message
 */
function setFieldState(input, msgEl, state, message = '') {
  input.classList.remove('is-valid', 'is-invalid', 'error');
  msgEl.className = 'field-message';
  msgEl.textContent = '';

  if (state === 'success') {
    input.classList.add('is-valid');
    msgEl.classList.add('success');
    msgEl.textContent = message;
  } else if (state === 'error') {
    input.classList.add('is-invalid', 'error');
    msgEl.classList.add('error');
    msgEl.textContent = message;
  } else if (state === 'hint') {
    msgEl.classList.add('hint');
    msgEl.textContent = message;
  }
}

/* ---- Individual field validators ---- */

function validateName(showSuccess = false) {
  const val = $nameInput.value;
  if (!val) { setFieldState($nameInput, $nameMsg, 'idle'); return false; }
  if (!isValidName(val)) {
    setFieldState($nameInput, $nameMsg, 'error', '⚠ Enter your full name (min 2 characters)');
    return false;
  }
  if (showSuccess) setFieldState($nameInput, $nameMsg, 'success', '✓ Looks good');
  else setFieldState($nameInput, $nameMsg, 'idle');
  return true;
}

function validateEmail(showSuccess = false) {
  const val = $emailInput.value;
  if (!val) { setFieldState($emailInput, $emailMsg, 'idle'); return false; }
  if (!isValidEmail(val)) {
    setFieldState($emailInput, $emailMsg, 'error', '⚠ Enter a valid email address');
    return false;
  }
  if (showSuccess) setFieldState($emailInput, $emailMsg, 'success', '✓ Valid email');
  else setFieldState($emailInput, $emailMsg, 'idle');
  return true;
}

function validatePassword(showSuccess = false) {
  const val = $passwordInput.value;
  if (!val) { setFieldState($passwordInput, $passwordMsg, 'idle'); return false; }
  if (!isValidPassword(val)) {
    setFieldState($passwordInput, $passwordMsg, 'error', '⚠ Password must be at least 8 characters');
    return false;
  }
  if (SignUp.strengthScore < 2) {
    setFieldState($passwordInput, $passwordMsg, 'error', '⚠ Please use a stronger password');
    return false;
  }
  if (showSuccess) setFieldState($passwordInput, $passwordMsg, 'success', '✓ Strong password');
  else setFieldState($passwordInput, $passwordMsg, 'idle');
  return true;
}

function validateConfirm(showSuccess = false) {
  const pass = $passwordInput.value;
  const conf = $confirmInput.value;
  if (!conf) { setFieldState($confirmInput, $confirmMsg, 'idle'); return false; }
  if (!passwordsMatch(pass, conf)) {
    setFieldState($confirmInput, $confirmMsg, 'error', '⚠ Passwords do not match');
    return false;
  }
  if (showSuccess) setFieldState($confirmInput, $confirmMsg, 'success', '✓ Passwords match');
  else setFieldState($confirmInput, $confirmMsg, 'idle');
  return true;
}

function validateAll() {
  const n = validateName(true);
  const e = validateEmail(true);
  const p = validatePassword(true);
  const c = validateConfirm(true);
  return n && e && p && c;
}

/* ============================================
   PASSWORD STRENGTH METER
   ============================================ */

const STRENGTH_LABELS = ['', 'Weak', 'Fair', 'Good', 'Strong'];
const STRENGTH_COLORS = ['', 'var(--rose-light)', 'var(--amber-light)', 'var(--cyan-light)', 'var(--emerald-light)'];

const CRITERIA = [
  { id: 'len',    label: '8+ chars',   test: v => v.length >= 8 },
  { id: 'upper',  label: 'Uppercase',  test: v => /[A-Z]/.test(v) },
  { id: 'num',    label: 'Number',     test: v => /\d/.test(v) },
  { id: 'symbol', label: 'Symbol',     test: v => /[^A-Za-z0-9]/.test(v) },
];

function calcStrength(password) {
  if (!password) return 0;
  let score = 0;
  CRITERIA.forEach(c => { if (c.test(password)) score++; });
  return score;
}

function renderStrength(password) {
  const score = calcStrength(password);
  SignUp.strengthScore = score;

  /* Toggle visibility */
  if ($strengthWrap) {
    $strengthWrap.style.display = password.length > 0 ? 'flex' : 'none';
  }

  if (!$strengthBars || !$strengthLabelText) return;

  /* Remove previous level classes */
  for (let i = 1; i <= 4; i++) $strengthBars.classList.remove(`strength-${i}`);
  if (score > 0) $strengthBars.classList.add(`strength-${score}`);

  /* Label */
  $strengthLabelText.textContent = score > 0 ? STRENGTH_LABELS[score] : '';
  $strengthLabelText.style.color = STRENGTH_COLORS[score] || 'var(--text-muted)';

  /* Per-criterion hints */
  if ($strengthHints) {
    $strengthHints.querySelectorAll('.strength-hint').forEach(hint => {
      const id = hint.dataset.criteria;
      const crit = CRITERIA.find(c => c.id === id);
      if (crit) hint.classList.toggle('met', crit.test(password));
    });
  }
}

/* ============================================
   PASSWORD VISIBILITY TOGGLES
   ============================================ */

function togglePassword() {
  SignUp.passwordVisible = !SignUp.passwordVisible;
  $passwordInput.type = SignUp.passwordVisible ? 'text' : 'password';
  $pwToggle.textContent = SignUp.passwordVisible ? '🙈' : '👁';
  $pwToggle.setAttribute('aria-label', SignUp.passwordVisible ? 'Hide password' : 'Show password');
}

function toggleConfirm() {
  SignUp.confirmVisible = !SignUp.confirmVisible;
  $confirmInput.type = SignUp.confirmVisible ? 'text' : 'password';
  $confirmToggle.textContent = SignUp.confirmVisible ? '🙈' : '👁';
  $confirmToggle.setAttribute('aria-label', SignUp.confirmVisible ? 'Hide password' : 'Show password');
}

/* ============================================
   SUBMIT BUTTON LOADING STATE
   ============================================ */

function setLoading(on) {
  SignUp.isLoading = on;
  $submitBtn.classList.toggle('loading', on);
  $submitBtn.disabled = on;
}

/* ============================================
   SUCCESS OVERLAY
   ============================================ */

function showSuccessOverlay(name, subtitle = 'Your Satquery.AI account is ready. Taking you to your dashboard now.') {
  if (!$successOverlay) return;
  const nameEl = $successOverlay.querySelector('.success-name');
  const subEl = $successOverlay.querySelector('.success-sub');
  if (nameEl) nameEl.textContent = name.split(' ')[0];
  if (subEl) subEl.textContent = subtitle;
  $successOverlay.classList.add('active');
}

/* ============================================
   SIMULATED SIGNUP FLOW
   (Replace with real fetch() to your FastAPI backend)
   ============================================ */

async function signUpWithSupabase(name, email, password) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: name }
    }
  });

  if (error) {
    throw error;
  }

  return {
    user: data.user,
    session: data.session || null,
  };
}

/* ============================================
   FORM SUBMIT HANDLER
   ============================================ */

async function handleSignUp(e) {
  e.preventDefault();
  if (SignUp.isLoading) return;

  /* Touch all fields */
  Object.keys(SignUp.fieldsTouched).forEach(k => { SignUp.fieldsTouched[k] = true; });

  /* Validate */
  if (!validateAll()) {
    Toast.warning('Almost there!', 'Please fix the highlighted fields before continuing.');
    shakeCard();
    return;
  }

  /* Terms check */
  if (!$termsChk.checked) {
    Toast.warning('Accept Terms', 'Please agree to our Terms of Service and Privacy Policy.');
    return;
  }

  const name     = $nameInput.value.trim();
  const email    = $emailInput.value.trim();
  const password = $passwordInput.value;

  setLoading(true);

  try {
    const result = await signUpWithSupabase(name, email, password);

    const authPayload = {
      user: result.user,
      token: result.session?.access_token || null,
    };

    Auth.storeAuth(authPayload, false);
    Auth.updateNavbarAuth();

    const hasSession = !!result.session;
    if (!hasSession) {
      Toast.success(
        `Thanks ${name.split(' ')[0]}!`,
        'Check your inbox to confirm your email before signing in.',
        6000
      );
      showSuccessOverlay(name, 'A confirmation email has been sent to your inbox. Confirm your account to continue.');
      setTimeout(() => {
        window.location.href = 'signin.html';
      }, 6000);
      return;
    }

    showSuccessOverlay(name, 'Your account is ready. Redirecting you to Analyze.');

    Toast.success(`Welcome to Satquery.AI, ${name.split(' ')[0]}!`, 'Your account is ready. Redirecting…', 4000);

    /* Redirect after delay */
    setTimeout(() => {
      window.location.href = getRedirectTarget('analysis.html');
    }, 2500);

  } catch (err) {
    setLoading(false);
    shakeCard();
    Toast.error('Signup Failed', err.message || 'Something went wrong. Please try again.');
    setFieldState($emailInput, $emailMsg, 'error', '⚠ ' + err.message);
  }
}

/* ============================================
   CARD SHAKE
   ============================================ */

function shakeCard() {
  const card = document.querySelector('.auth-card');
  if (!card) return;
  card.style.animation = 'none';
  requestAnimationFrame(() => {
    card.style.animation = 'cardShake 0.45s ease';
  });
}

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
   OAUTH STUBS
   ============================================ */

function handleGoogleSignUp() {
  Toast.info('Google Sign Up', 'OAuth flow would launch here in production.', 3000);
}

function handleGithubSignUp() {
  Toast.info('GitHub Sign Up', 'OAuth flow would launch here in production.', 3000);
}

/* ============================================
   INPUT GLOW EFFECTS
   ============================================ */

function initInputGlows() {
  document.querySelectorAll('.input-wrap .form-control').forEach(input => {
    const wrap = input.closest('.input-wrap');
    input.addEventListener('focus', () => {
      wrap.style.filter = 'drop-shadow(0 0 8px rgba(6,182,212,0.2))';
    });
    input.addEventListener('blur', () => {
      wrap.style.filter = '';
    });
  });
}

/* ============================================
   KEYBOARD SHORTCUT
   ============================================ */
function getRedirectTarget(defaultTarget = 'analysis.html') {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get('redirect');
  if (!redirect) return defaultTarget;
  return redirect;
}
function initKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      $form.requestSubmit();
    }
  });
}

/* ============================================
   CARD ENTRY ANIMATION
   ============================================ */

function animateCardEntry() {
  const card = document.querySelector('.auth-card');
  if (!card) return;
  card.style.opacity = '0';
  card.style.transform = 'translateY(24px)';
  requestAnimationFrame(() => {
    setTimeout(() => {
      card.style.transition = 'opacity 0.65s cubic-bezier(0.16,1,0.3,1), transform 0.65s cubic-bezier(0.16,1,0.3,1)';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 120);
  });
}

/* ============================================
   INIT
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
  /* Cache DOM */
  $form           = document.getElementById('signup-form');
  $nameInput      = document.getElementById('full-name');
  $emailInput     = document.getElementById('email');
  $passwordInput  = document.getElementById('password');
  $confirmInput   = document.getElementById('confirm-password');
  $termsChk       = document.getElementById('terms');
  $submitBtn      = document.getElementById('signup-btn');
  $pwToggle       = document.getElementById('pw-toggle');
  $confirmToggle  = document.getElementById('confirm-toggle');
  $nameMsg        = document.getElementById('name-msg');
  $emailMsg       = document.getElementById('email-msg');
  $passwordMsg    = document.getElementById('password-msg');
  $confirmMsg     = document.getElementById('confirm-msg');
  $strengthWrap   = document.getElementById('strength-wrap');
  $strengthBars   = document.getElementById('strength-bars');
  $strengthLabelText = document.getElementById('strength-label-text');
  $strengthHints  = document.getElementById('strength-hints');
  $successOverlay = document.getElementById('success-overlay');

  if (!$form) return;

  injectShakeKeyframe();
  animateCardEntry();
  initInputGlows();
  initKeyboardShortcuts();

  /* --- Form submit --- */
  $form.addEventListener('submit', handleSignUp);

  /* --- Password toggles --- */
  if ($pwToggle)      $pwToggle.addEventListener('click', togglePassword);
  if ($confirmToggle) $confirmToggle.addEventListener('click', toggleConfirm);

  /* --- OAuth --- */
  const gBtn = document.getElementById('btn-google');
  const ghBtn = document.getElementById('btn-github');
  if (gBtn)  gBtn.addEventListener('click', handleGoogleSignUp);
  if (ghBtn) ghBtn.addEventListener('click', handleGithubSignUp);

  /* --- Live validation (fires on input only AFTER field is first touched) --- */

  /* Name */
  $nameInput.addEventListener('blur', () => { SignUp.fieldsTouched.name = true; validateName(false); });
  $nameInput.addEventListener('input', () => { if (SignUp.fieldsTouched.name) validateName(false); });

  /* Email */
  $emailInput.addEventListener('blur', () => { SignUp.fieldsTouched.email = true; validateEmail(false); });
  $emailInput.addEventListener('input', () => { if (SignUp.fieldsTouched.email) validateEmail(false); });

  /* Password — also drives strength meter */
  $passwordInput.addEventListener('focus', () => {
    if ($strengthWrap && $passwordInput.value.length > 0) $strengthWrap.style.display = 'flex';
  });
  $passwordInput.addEventListener('input', () => {
    renderStrength($passwordInput.value);
    if (SignUp.fieldsTouched.password) validatePassword(false);
    /* Re-validate confirm if user edits password */
    if (SignUp.fieldsTouched.confirm && $confirmInput.value) validateConfirm(false);
  });
  $passwordInput.addEventListener('blur', () => {
    SignUp.fieldsTouched.password = true;
    validatePassword(false);
  });

  /* Confirm password */
  $confirmInput.addEventListener('blur', () => { SignUp.fieldsTouched.confirm = true; validateConfirm(false); });
  $confirmInput.addEventListener('input', () => { if (SignUp.fieldsTouched.confirm) validateConfirm(false); });

  /* Initial strength meter hidden */
  if ($strengthWrap) $strengthWrap.style.display = 'none';
});