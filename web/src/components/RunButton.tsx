import styles from './RunButton.module.css';

interface Props {
  disabled: boolean;
  submitting: boolean;
  count: number;
  onRun: () => void;
}

export function RunButton({ disabled, submitting, count, onRun }: Props) {
  return (
    <button className={`btn btn-primary ${styles.run}`} disabled={disabled} onClick={onRun}>
      {submitting ? 'Starting…' : `Forge ${count} clip${count === 1 ? '' : 's'} →`}
    </button>
  );
}
