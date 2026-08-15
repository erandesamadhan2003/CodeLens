import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/ui/Button';

export default function CTASection() {
  const navigate = useNavigate();
  return (
    <section className="w-full bg-ink py-20 px-6 flex flex-col items-center text-center">
      <div className="w-full max-w-[640px] flex flex-col items-center gap-10">
        <h2 className="font-display font-bold text-4xl lg:text-[56px] leading-[1.1] uppercase text-paper tracking-tight">
          Audit your codebase in minutes, not a Tuesday afternoon.
        </h2>
        <Button variant="light" size="lg" onClick={() => navigate('/login')}>
          CONNECT REPO ↗
        </Button>
      </div>
    </section>
  );
}
