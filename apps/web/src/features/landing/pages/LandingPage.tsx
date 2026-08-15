import React from 'react';
import HeroSection from '../components/Overview';
import SecurityEngine from '../components/SecurityEngine';
import DepraSection from '../components/DepraSection';
import DevoraSection from '../components/DevoraSection';
import DocryxSection from '../components/DocryxSection';
import InfrastructureEngine from '../components/InfrastructureEngine';
import CTASection from '../components/CTASection';
import Footer from '../components/Footer';

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
