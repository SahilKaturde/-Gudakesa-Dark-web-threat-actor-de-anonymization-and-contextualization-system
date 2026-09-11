import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { register, login } = useAuth();
  const navigate = useNavigate();

  const canvasRef = useRef(null);

  // Rotating ASCII galaxy
  useEffect(() => {
    const pre = canvasRef.current;
    if (!pre) return;

    let animationId;
    let lastFrame = 0;
    const FRAME_INTERVAL = 1000 / 20;

    const COLS = 90;
    const ROWS = 45;

    const CENTER_X = COLS / 2;
    const CENTER_Y = ROWS / 2;
    const ARMS = 2;
    const SPIN = 0.6;
    const MAX_R = 18;

    const seedRandom = (x, y) => {
      const n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
      return n - Math.floor(n);
    };

    const render = (t) => {
      animationId = requestAnimationFrame(render);
      if (t - lastFrame < FRAME_INTERVAL) return;
      lastFrame = t;

      const angle0 = t * 0.00012;
      let out = '';

      for (let y = 0; y < ROWS; y++) {
        let line = '';
        for (let x = 0; x < COLS; x++) {
          const dx = (x - CENTER_X) / 1.0;
          const dy = (y - CENTER_Y) * 2.0;
          const r = Math.sqrt(dx * dx + dy * dy);

          let ch = ' ';

          if (r < MAX_R + 2) {
            const theta = Math.atan2(dy, dx);
            const armPhase = ARMS * (theta + SPIN * Math.log(r + 0.6)) + angle0;
            const arm = Math.cos(armPhase);
            const armDensity = Math.pow(Math.max(arm, 0), 3);
            const radial = Math.exp(-r / 7) * Math.exp(-Math.pow(r / MAX_R, 3));
            const n = seedRandom(x, y);
            const intensity = armDensity * radial * (0.6 + 0.8 * n);
            const core = r < 2 ? 0.9 - r * 0.25 : 0;
            const total = Math.min(1, intensity + core);

            if (total > 0.68) ch = '@';
            else if (total > 0.52) ch = '#';
            else if (total > 0.38) ch = '*';
            else if (total > 0.26) ch = '+';
            else if (total > 0.16) ch = '.';
            else if (total > 0.08) ch = "'";
            else if (total > 0.03) ch = '`';
          }

          line += ch;
        }
        out += line + '\n';
      }

      pre.textContent = out;
    };

    animationId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationId);
  }, []);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      await register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });

      await login(formData.username, formData.password);
      navigate('/', { replace: true });
    } catch (err) {
      console.error('Registration error:', err);
      if (err.response?.data) {
        const errorData = err.response.data;
        const firstErrorKey = Object.keys(errorData)[0];
        const errorMsg = Array.isArray(errorData[firstErrorKey])
          ? `${firstErrorKey}: ${errorData[firstErrorKey][0]}`
          : errorData[firstErrorKey] || 'Registration failed.';
        setError(errorMsg);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-white px-4 py-12 text-black font-mono overflow-hidden">
      {/* Star dust: tiny stray dots scattered across the page */}
      <div
        aria-hidden="true"
        className="pointer-events-none select-none absolute inset-0 opacity-[0.10] text-[10px] leading-[14px] font-mono text-black whitespace-pre overflow-hidden"
      >
        {Array.from({ length: 60 }).map((_, i) => {
          const top = (i * 137) % 100;
          const left = (i * 73) % 100;
          const ch = i % 7 === 0 ? '.' : i % 5 === 0 ? '+' : "'";
          return (
            <span
              key={i}
              className="absolute"
              style={{ top: `${top}%`, left: `${left}%` }}
            >
              {ch}
            </span>
          );
        })}
      </div>

      {/* The galaxy (behind the card, slightly right of center) */}
      <pre
        ref={canvasRef}
        aria-hidden="true"
        className="pointer-events-none select-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 m-0 p-0 text-[10px] leading-[10px] font-mono text-black opacity-[0.22] whitespace-pre"
      />

      {/* Green tinted overlay */}
      <div
        aria-hidden="true"
        className="pointer-events-none select-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[540px] h-[450px] opacity-[0.10]"
        style={{
          background:
            'radial-gradient(circle at 50% 50%, rgba(22,163,74,0.9) 0%, rgba(22,163,74,0.35) 25%, rgba(22,163,74,0) 60%)',
          mixBlendMode: 'multiply',
        }}
      />

      {/* Yellow tinted overlay */}
      <div
        aria-hidden="true"
        className="pointer-events-none select-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[360px] h-[300px] opacity-[0.14]"
        style={{
          background:
            'radial-gradient(circle at 42% 48%, rgba(234,179,8,0.9) 0%, rgba(234,179,8,0.35) 30%, rgba(234,179,8,0) 65%)',
          mixBlendMode: 'multiply',
        }}
      />

      {/* Register card */}
      <div className="relative w-full max-w-md bg-white border-4 border-black shadow-[10px_10px_0_0_#000] p-6 sm:p-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-black uppercase tracking-tight text-black">
            Create an Account
          </h2>
          <p className="text-sm text-neutral-600 font-medium mt-1">
            Get started with your account
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-200 border-2 border-black text-black text-sm font-bold shadow-[3px_3px_0_0_#000]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              className="block text-sm font-black uppercase tracking-wider text-black mb-1.5"
              htmlFor="username"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              value={formData.username}
              onChange={handleChange}
              className="w-full px-4 py-2.5 bg-white border-2 border-black text-black placeholder-neutral-500 focus:outline-none focus:ring-0 focus:border-black focus:shadow-[4px_4px_0_0_#000] transition-shadow font-mono"
              placeholder="johndoe"
            />
          </div>

          <div>
            <label
              className="block text-sm font-black uppercase tracking-wider text-black mb-1.5"
              htmlFor="email"
            >
              Email Address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              value={formData.email}
              onChange={handleChange}
              className="w-full px-4 py-2.5 bg-white border-2 border-black text-black placeholder-neutral-500 focus:outline-none focus:ring-0 focus:border-black focus:shadow-[4px_4px_0_0_#000] transition-shadow font-mono"
              placeholder="john@example.com"
            />
          </div>

          <div>
            <label
              className="block text-sm font-black uppercase tracking-wider text-black mb-1.5"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              value={formData.password}
              onChange={handleChange}
              className="w-full px-4 py-2.5 bg-white border-2 border-black text-black placeholder-neutral-500 focus:outline-none focus:ring-0 focus:border-black focus:shadow-[4px_4px_0_0_#000] transition-shadow font-mono"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label
              className="block text-sm font-black uppercase tracking-wider text-black mb-1.5"
              htmlFor="confirmPassword"
            >
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              required
              value={formData.confirmPassword}
              onChange={handleChange}
              className="w-full px-4 py-2.5 bg-white border-2 border-black text-black placeholder-neutral-500 focus:outline-none focus:ring-0 focus:border-black focus:shadow-[4px_4px_0_0_#000] transition-shadow font-mono"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-4 py-2.5 px-4 bg-black border-2 border-black text-white font-black uppercase tracking-wider shadow-[4px_4px_0_0_#000] hover:bg-neutral-800 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
          >
            {isSubmitting ? 'Registering...' : 'Create Account'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-neutral-600">
          Already have an account?{' '}
          <Link
            to="/login"
            className="text-black font-bold border-b-2 border-black hover:bg-yellow-300 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Register;