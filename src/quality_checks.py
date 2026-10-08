"""
Quality checks, validation, and diagnostics for the unified IPP panel.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union

import pandas as pd
import numpy as np

try:
    from src.config import COL_DATE, COL_CIIU, COL_IPP
except ImportError:
    # Fallback default column names
    COL_DATE = 'fecha'
    COL_CIIU = 'ciiu_codigo'
    COL_IPP = 'ipp'

logger = logging.getLogger(__name__)

class PanelValidator:
    """Validate and diagnose panel data issues like missing values, gaps, and outliers."""

    def __init__(self, df: pd.DataFrame, 
                 date_col: str = COL_DATE,
                 ciiu_col: str = COL_CIIU, 
                 ipp_col: str = COL_IPP):
        self.df = df.copy()
        self.date_col = date_col
        self.ciiu_col = ciiu_col
        self.ipp_col = ipp_col

        if not pd.api.types.is_datetime64_any_dtype(self.df[self.date_col]):
            self.df[self.date_col] = pd.to_datetime(self.df[self.date_col])

    def check_balance(self) -> pd.DataFrame:
        """
        Check if panel is balanced (all sectors have same date range).
        
        Returns:
            DataFrame with sector, start_date, end_date, n_obs, n_missing, pct_complete.
        """
        agg = self.df.groupby(self.ciiu_col).agg(
            start_date=(self.date_col, 'min'),
            end_date=(self.date_col, 'max'),
            n_obs=(self.date_col, 'count')
        ).reset_index()
        
        global_start = agg['start_date'].min()
        global_end = agg['end_date'].max()
        
        # Calculate theoretical number of months
        # Add 1 month to include the end date if it falls exactly on month start
        total_months = len(pd.date_range(start=global_start, end=global_end, freq='MS'))
        
        agg['expected_obs'] = agg.apply(
            lambda x: len(pd.date_range(start=x['start_date'], end=x['end_date'], freq='MS')), 
            axis=1
        )
        agg['n_missing'] = agg['expected_obs'] - agg['n_obs']
        agg['pct_complete'] = (agg['n_obs'] / agg['expected_obs'] * 100).round(2)
        
        return agg

    def check_gaps(self) -> pd.DataFrame:
        """
        Identify temporal gaps within each sector's series.
        
        Returns:
            DataFrame with sector, gap_start, gap_end, gap_months.
        """
        self.df = self.df.sort_values(by=[self.ciiu_col, self.date_col])
        
        self.df['prev_date'] = self.df.groupby(self.ciiu_col)[self.date_col].shift(1)
        
        # Determine gap months approximately
        self.df['gap_months'] = ((self.df[self.date_col].dt.year - self.df['prev_date'].dt.year) * 12 + 
                                 (self.df[self.date_col].dt.month - self.df['prev_date'].dt.month) - 1)
        
        gaps = self.df[self.df['gap_months'] > 0].copy()
        gaps['gap_start'] = gaps['prev_date'] + pd.DateOffset(months=1)
        gaps['gap_end'] = gaps[self.date_col] - pd.DateOffset(months=1)
        
        res = gaps[[self.ciiu_col, 'gap_start', 'gap_end', 'gap_months']]
        self.df.drop(columns=['prev_date', 'gap_months'], inplace=True)
        return res

    def check_duplicates(self) -> pd.DataFrame:
        """
        Find duplicate (fecha, ciiu_codigo) pairs.
        
        Returns:
            DataFrame of duplicated rows.
        """
        dupes = self.df[self.df.duplicated(subset=[self.ciiu_col, self.date_col], keep=False)]
        return dupes.sort_values(by=[self.ciiu_col, self.date_col])

    def check_missing_values(self) -> pd.DataFrame:
        """
        Summary of NaN/null IPP values by sector and year.
        
        Returns:
            DataFrame summarizing missing IPP counts.
        """
        self.df['year'] = self.df[self.date_col].dt.year
        missing = self.df[self.df[self.ipp_col].isna()]
        
        res = missing.groupby([self.ciiu_col, 'year']).size().reset_index(name='missing_count')
        self.df.drop(columns=['year'], inplace=True)
        return res

    def check_outliers(
        self, 
        method: str = 'iqr',
        threshold: float = 3.0
    ) -> pd.DataFrame:
        """
        Detect outlier IPP values.
        
        Args:
            method: 'iqr', 'zscore', or 'growth_rate'
            threshold: multiplier for IQR/Z-score limit
            
        Returns:
            DataFrame with flagged observations and diagnostics.
        """
        res = self.df.copy()
        
        if method == 'iqr':
            q1 = res.groupby(self.ciiu_col)[self.ipp_col].transform(lambda x: x.quantile(0.25))
            q3 = res.groupby(self.ciiu_col)[self.ipp_col].transform(lambda x: x.quantile(0.75))
            iqr = q3 - q1
            res['is_outlier'] = (res[self.ipp_col] < (q1 - threshold * iqr)) | (res[self.ipp_col] > (q3 + threshold * iqr))
            
        elif method == 'zscore':
            mean = res.groupby(self.ciiu_col)[self.ipp_col].transform('mean')
            std = res.groupby(self.ciiu_col)[self.ipp_col].transform('std')
            res['zscore'] = (res[self.ipp_col] - mean) / std
            res['is_outlier'] = res['zscore'].abs() > threshold
            
        elif method == 'growth_rate':
            res = res.sort_values([self.ciiu_col, self.date_col])
            res['growth'] = res.groupby(self.ciiu_col)[self.ipp_col].pct_change()
            g_mean = res.groupby(self.ciiu_col)['growth'].transform('mean')
            g_std = res.groupby(self.ciiu_col)['growth'].transform('std')
            res['g_zscore'] = (res['growth'] - g_mean) / g_std
            res['is_outlier'] = res['g_zscore'].abs() > threshold
        else:
            raise ValueError(f"Unknown method {method}")
            
        outliers = res[res['is_outlier']].copy()
        return outliers

    def check_monotonicity_breaks(self) -> pd.DataFrame:
        """
        Identify periods where IPP trends reverse dramatically,
        which might indicate splice errors.
        
        Returns:
            DataFrame containing rows where severe reversals occurred.
        """
        res = self.df.copy()
        res = res.sort_values([self.ciiu_col, self.date_col])
        res['growth'] = res.groupby(self.ciiu_col)[self.ipp_col].pct_change()
        
        res['prev_growth'] = res.groupby(self.ciiu_col)['growth'].shift(1)
        res['growth_diff'] = (res['growth'] - res['prev_growth']).abs()
        
        # Consider a break if growth diff is highly abnormal (e.g., > 3 std devs of the diff)
        diff_mean = res.groupby(self.ciiu_col)['growth_diff'].transform('mean')
        diff_std = res.groupby(self.ciiu_col)['growth_diff'].transform('std')
        
        # Adding a minimum absolute threshold to ignore small noise
        res['is_break'] = (res['growth_diff'] > diff_mean + 3 * diff_std) & (res['growth_diff'] > 0.1)
        
        return res[res['is_break']].copy()

    def check_cross_sectional_dispersion(self, freq: str = 'Y') -> pd.DataFrame:
        """
        Compute cross-sectional statistics of IPP levels across sectors for each period.
        
        Args:
            freq: 'Y' for annual, 'M' for monthly, etc.
            
        Returns:
            DataFrame with period statistics.
        """
        df_period = self.df.copy()
        df_period['period'] = df_period[self.date_col].dt.to_period(freq)
        
        stats = df_period.groupby('period')[self.ipp_col].agg(
            mean='mean',
            std='std',
            min='min',
            max='max'
        ).reset_index()
        
        stats['cv'] = stats['std'] / stats['mean']
        return stats

    def full_diagnostic(self) -> dict:
        """
        Run all checks and return a comprehensive diagnostic dict.
        """
        return {
            'balance': self.check_balance(),
            'gaps': self.check_gaps(),
            'duplicates': self.check_duplicates(),
            'missing_values': self.check_missing_values(),
            'outliers_iqr': self.check_outliers('iqr'),
            'outliers_growth': self.check_outliers('growth_rate'),
            'monotonicity_breaks': self.check_monotonicity_breaks(),
            'dispersion': self.check_cross_sectional_dispersion()
        }

    def summary_report(self) -> str:
        """
        Generate a human-readable summary report string.
        """
        diagnostics = self.full_diagnostic()
        
        report = []
        report.append("=== IPP Panel Quality Summary ===")
        
        bal = diagnostics['balance']
        report.append(f"\n[Balance]")
        report.append(f"Total Sectors: {len(bal)}")
        report.append(f"Sectors perfectly complete: {len(bal[bal['n_missing'] == 0])}")
        
        gaps = diagnostics['gaps']
        report.append(f"\n[Gaps]")
        report.append(f"Total internal gaps identified: {len(gaps)}")
        
        dupes = diagnostics['duplicates']
        report.append(f"\n[Duplicates]")
        report.append(f"Duplicate records: {len(dupes)}")
        
        miss = diagnostics['missing_values']
        report.append(f"\n[Missing Values]")
        report.append(f"Sectors with missing IPP: {miss[self.ciiu_col].nunique()}")
        
        outliers = diagnostics['outliers_growth']
        report.append(f"\n[Growth Outliers]")
        report.append(f"Extreme growth observations detected: {len(outliers)}")
        
        breaks = diagnostics['monotonicity_breaks']
        report.append(f"\n[Monotonicity Breaks]")
        report.append(f"Potential splice trend reversals: {len(breaks)}")
        
        return "\n".join(report)


class PanelExporter:
    """Export the final panel in multiple formats."""
    
    def __init__(self, df: pd.DataFrame, output_dir: Union[str, Path]):
        self.df = df.copy()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def to_parquet(self, filename: str = 'ipp_panel_colombia.parquet') -> Path:
        out_path = self.output_dir / filename
        try:
            self.df.to_parquet(out_path, index=False)
            logger.info(f"Exported to Parquet: {out_path}")
        except ImportError:
            logger.error("pyarrow or fastparquet not installed. Skipping parquet export.")
        return out_path

    def to_csv(self, filename: str = 'ipp_panel_colombia.csv') -> Path:
        out_path = self.output_dir / filename
        self.df.to_csv(out_path, index=False, encoding='utf-8')
        logger.info(f"Exported to CSV: {out_path}")
        return out_path

    def to_stata(self, filename: str = 'ipp_panel_colombia.dta') -> Path:
        """Export to Stata .dta format. Handles Stata limitations."""
        out_path = self.output_dir / filename
        export_df = self.df.copy()
        
        # Convert objects/strings
        for col in export_df.select_dtypes(['object', 'string']).columns:
            export_df[col] = export_df[col].astype(str).str[:244] # Stata max str len is typically 244 for strL compatibility 
            
        # Rename columns to meet Stata <= 32 char limit and no spaces
        new_cols = {col: col.replace(' ', '_').replace('.', '_')[:32] for col in export_df.columns}
        export_df.rename(columns=new_cols, inplace=True)
        
        export_df.to_stata(out_path, write_index=False, version=118)
        logger.info(f"Exported to Stata: {out_path}")
        return out_path

    def to_excel(self, filename: str = 'ipp_panel_colombia.xlsx') -> Path:
        out_path = self.output_dir / filename
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            self.df.to_excel(writer, sheet_name='IPP_Panel', index=False)
            
            # Add metadata sheet
            meta = self.generate_metadata()
            meta_df = pd.DataFrame(list(meta.items()), columns=['Property', 'Value'])
            meta_df.to_excel(writer, sheet_name='Metadata', index=False)
            
        logger.info(f"Exported to Excel: {out_path}")
        return out_path

    def export_all(self) -> Dict[str, Path]:
        """Export in all formats."""
        paths = {
            'csv': self.to_csv(),
            'excel': self.to_excel(),
            'stata': self.to_stata()
        }
        # Parquet depends on pyarrow/fastparquet
        try:
            import pyarrow
            paths['parquet'] = self.to_parquet()
        except ImportError:
            pass
            
        return paths

    def generate_metadata(self) -> dict:
        """Generate metadata dictionary."""
        date_col_exists = COL_DATE in self.df.columns
        ciiu_col_exists = COL_CIIU in self.df.columns
        
        min_date = self.df[COL_DATE].min().strftime('%Y-%m-%d') if date_col_exists else 'N/A'
        max_date = self.df[COL_DATE].max().strftime('%Y-%m-%d') if date_col_exists else 'N/A'
        n_sectors = self.df[COL_CIIU].nunique() if ciiu_col_exists else 'N/A'
        
        return {
            'Date Range': f"{min_date} to {max_date}",
            'Number of Sectors': n_sectors,
            'Number of Observations': len(self.df),
            'Generation Timestamp': datetime.now().isoformat(),
        }
