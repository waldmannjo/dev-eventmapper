"""
Validation script for Phase 1 improvements.
Compares old vs. new mapping pipeline on validation set.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.mapper import run_mapping_step4
from openai import OpenAI

def load_validation_data():
    """Load and split historical data into train/validation."""
    hist_file = "examples/CES_Umschlüsselungseinträge_all.xlsx"

    if not os.path.exists(hist_file):
        print(f"Error: {hist_file} not found")
        return None, None

    df = pd.read_excel(hist_file)
    df = df.dropna(subset=['Description', 'AEB Event Code'])

    # Filter out classes with fewer than 2 members (can't stratify with singletons)
    code_counts = df['AEB Event Code'].value_counts()
    valid_codes = code_counts[code_counts >= 2].index
    excluded = len(df) - df['AEB Event Code'].isin(valid_codes).sum()
    if excluded > 0:
        print(f"Note: Excluding {excluded} rows with singleton AEB codes from stratified split")
    df = df[df['AEB Event Code'].isin(valid_codes)]

    train_df, val_df = train_test_split(
        df,
        test_size=0.2,
        stratify=df['AEB Event Code'],
        random_state=42
    )

    print(f"Training set: {len(train_df)} samples")
    print(f"Validation set: {len(val_df)} samples")

    return train_df, val_df

def run_validation(client, val_df, model_name="gpt-4o-mini"):
    """Run mapping on validation set and compute metrics."""

    val_input = val_df.copy().reset_index(drop=True)
    val_input['Beschreibung'] = val_input['Description']

    print("\nRunning mapping on validation set...")
    result_df = run_mapping_step4(
        client,
        val_input,
        model_name=model_name,
        threshold=0.60
    )

    y_true = val_df['AEB Event Code'].values
    y_pred = result_df['final_code'].values

    accuracy = accuracy_score(y_true, y_pred)

    print("\n" + "="*60)
    print("PHASE 1 VALIDATION RESULTS")
    print("="*60)
    print(f"\nOverall Accuracy: {accuracy:.2%}")

    conf_scores = result_df['confidence'].values
    print(f"\nConfidence Distribution:")
    print(f"  Mean: {np.mean(conf_scores):.3f}")
    print(f"  Median: {np.median(conf_scores):.3f}")
    print(f"  Std: {np.std(conf_scores):.3f}")

    source_counts = result_df['source'].value_counts()
    print(f"\nPrediction Sources:")
    for source, count in source_counts.items():
        pct = 100 * count / len(result_df)
        print(f"  {source}: {count} ({pct:.1f}%)")

    high_conf_mask = conf_scores >= 0.8
    low_conf_mask = conf_scores < 0.6

    if high_conf_mask.any():
        high_conf_acc = accuracy_score(y_true[high_conf_mask], y_pred[high_conf_mask])
        print(f"\nHigh Confidence (>=0.8) Accuracy: {high_conf_acc:.2%} (n={high_conf_mask.sum()})")

    if low_conf_mask.any():
        low_conf_acc = accuracy_score(y_true[low_conf_mask], y_pred[low_conf_mask])
        print(f"Low Confidence (<0.6) Accuracy: {low_conf_acc:.2%} (n={low_conf_mask.sum()})")

    print("\n" + "="*60)

    print("\nDetailed Classification Report:")
    print(classification_report(y_true, y_pred, zero_division=0))

    # --- Per-stage accuracy breakdown ---
    print("\n" + "="*60)
    print("PER-STAGE ACCURACY BREAKDOWN")
    print("="*60)
    for stage in ['history-knn', 'emb+ce', 'llm-batch']:
        mask = result_df['source'] == stage
        if mask.any():
            stage_acc = accuracy_score(y_true[mask], y_pred[mask])
            print(f"  {stage}: {stage_acc:.2%} (n={mask.sum()})")
        else:
            print(f"  {stage}: no predictions (n=0)")

    # --- Confusion matrix: top confused pairs ---
    print("\n" + "="*60)
    print("TOP CONFUSED PAIRS (off-diagonal confusion matrix)")
    print("="*60)
    all_codes = sorted(c for c in set(list(y_true) + list(y_pred)) if c is not None)
    cm = confusion_matrix(y_true, y_pred, labels=all_codes)

    # Extract off-diagonal entries as (true_label, pred_label, count) tuples
    confusion_pairs = []
    for i, true_label in enumerate(all_codes):
        for j, pred_label in enumerate(all_codes):
            if i != j and cm[i, j] > 0:
                confusion_pairs.append((true_label, pred_label, cm[i, j]))

    # Sort by count descending, take top 15
    confusion_pairs.sort(key=lambda x: x[2], reverse=True)
    top_n = 15
    top_pairs = confusion_pairs[:top_n]

    if top_pairs:
        print(f"\n{'True':>8}  {'Predicted':>10}  {'Count':>6}")
        print("-" * 32)
        for true_label, pred_label, count in top_pairs:
            print(f"  {true_label:>6}  ->  {pred_label:<10}  {count:>5}")
    else:
        print("  No confusion pairs found (perfect accuracy or empty result).")

    # --- Error examples per confused pair ---
    print("\n" + "="*60)
    print("ERROR EXAMPLES PER CONFUSED PAIR (top pairs, up to 3 examples each)")
    print("="*60)

    # Build a combined frame: original descriptions + predictions + ground truth
    # val_descriptions is reset to 0-based index here; result_df preserves val_input's
    # 0-based index. Both align positionally with y_true/y_pred numpy arrays.
    val_descriptions = val_df['Description'].reset_index(drop=True)

    for true_label, pred_label, count in top_pairs[:10]:
        error_mask = (
            (np.array(y_true) == true_label) &
            (np.array(y_pred) == pred_label)
        )
        error_indices = np.where(error_mask)[0]
        print(f"\n  True={true_label} -> Predicted={pred_label}  ({count} errors)")
        example_limit = min(3, len(error_indices))
        for k in range(example_limit):
            idx = error_indices[k]
            desc = val_descriptions.iloc[idx] if idx < len(val_descriptions) else "<unavailable>"
            conf = conf_scores[idx]
            src = result_df['source'].iloc[idx]
            # Truncate long descriptions for readability
            desc_str = str(desc)
            if len(desc_str) > 120:
                desc_str = desc_str[:117] + "..."
            print(f"    [{k+1}] conf={conf:.3f} src={src}")
            print(f"         desc: {desc_str}")

    return accuracy, result_df

def main():
    """Main validation workflow."""
    print("Phase 1 Validation - Quick Wins")
    print("="*60)

    train_df, val_df = load_validation_data()
    if val_df is None:
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        return

    client = OpenAI(api_key=api_key)

    accuracy, result_df = run_validation(client, val_df)

    output_file = "validation_results_phase1.csv"
    result_df.to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

    print("\n" + "="*60)
    print("PHASE 1 SUCCESS CRITERIA")
    print("="*60)

    baseline_accuracy = 0.75
    improvement = accuracy - baseline_accuracy

    print(f"Baseline Accuracy: {baseline_accuracy:.2%}")
    print(f"Current Accuracy: {accuracy:.2%}")
    print(f"Improvement: {improvement:+.2%}")

    target_improvement = 0.10
    if improvement >= target_improvement:
        print(f"\nSUCCESS: Achieved {improvement:.2%} improvement (target: {target_improvement:.2%})")
    else:
        print(f"\nNEEDS WORK: Only {improvement:.2%} improvement (target: {target_improvement:.2%})")

if __name__ == "__main__":
    main()
