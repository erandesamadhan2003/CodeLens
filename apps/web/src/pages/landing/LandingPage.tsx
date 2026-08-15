import React from 'react';
import HeroSection from './sections/Overview';
import SecurityEngine from './sections/SecurityEngine';
import DepraSection from './sections/DepraSection';
import DevoraSection from './sections/DevoraSection';
import DocryxSection from './sections/DocryxSection';
import InfrastructureEngine from './sections/InfrastructureEngine';
import CTASection from './sections/CTASection';
import Footer from './sections/Footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper font-sans text-ink">
      <HeroSection />
      <SecurityEngine />
      <DepraSection />
      <DevoraSection />
      <DocryxSection />
      <InfrastructureEngine />
      <CTASection />
      <Footer />
    </div>
  );
}
