/**
 * Tests for <DeviceTagList>.
 *
 * Covers:
 * - Empty tags renders a "—" placeholder
 * - Each tag is rendered as a badge
 * - Multiple tags all appear
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DeviceTagList } from './DeviceTagList';

describe('<DeviceTagList>', () => {
  it('renders "—" when tags array is empty', () => {
    render(<DeviceTagList tags={[]} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('renders a badge for each tag', () => {
    render(<DeviceTagList tags={['core', 'prod', 'mpls']} />);
    expect(screen.getByText('core')).toBeInTheDocument();
    expect(screen.getByText('prod')).toBeInTheDocument();
    expect(screen.getByText('mpls')).toBeInTheDocument();
  });

  it('renders a single tag', () => {
    render(<DeviceTagList tags={['edge']} />);
    expect(screen.getByText('edge')).toBeInTheDocument();
  });

  it('does not render "—" when tags are present', () => {
    render(<DeviceTagList tags={['tag1']} />);
    expect(screen.queryByText('—')).not.toBeInTheDocument();
  });
});
