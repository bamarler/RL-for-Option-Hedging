import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from MCPG import MCPGAgent
from option_gym import OptionEnv
import pandas as pd

# Set up environment and agent
env = OptionEnv(tickers=['AAPL', 'MSFT', 'IBM', 'JNJ', 'MCD', 
                        'KO', 'PG', 'WMT', 'XOM', 'GE', 
                        'MMM', 'F', 'T', 'CSCO', 'PFE',
                        'INTC', 'BA', 'CAT', 'CVX', 'PEP'], verbose=False)

agent = MCPGAgent()
agent.load_policy('MCPGPolicy.pkl')
# agent.plot_train_statistics('MCPGTrainStatistics.csv')

# Run multiple test episodes
num_episodes = 1000
results = {
    'returns': [],
    'final_pnls': [],
    'option_payoffs': [],
    'hedging_pnls': [],
    'premiums_paid': [],
    'tickers': [],
    'initial_expiry_days': [],
    'optimal_max_returns': [],
    'optimal_min_returns': []
}

print(f"Running {num_episodes} test episodes...")

for episode in range(num_episodes):
    obs, _ = env.reset()
    done = False
    
    # Store initial conditions
    initial_expiry = env.time_to_expiry
    initial_investment = env.premium_per_share * env.number_of_shares * env.risk
    
    # Get optimal PNLs for this episode
    max_return, min_return = env.compute_optimal_pnls()
    
    trajectory = {
        'positions': [],
        'stock_prices': []
    }
    
    while not done:
        action, _ = agent.select_action(obs, training=False)
        
        # Store trajectory data
        position = env.action_space[action]
        stock_price = obs['normalized_stock_price'] * env.strike_price
        
        trajectory['positions'].append(position)
        trajectory['stock_prices'].append(stock_price)
        
        obs, reward, done, truncated, _ = env.step(action)
        done = done or truncated
    
    # Calculate final metrics
    final_price = trajectory['stock_prices'][-1]
    option_payoff = max(env.strike_price - final_price, 0) * env.number_of_shares
    
    # Calculate hedging P&L
    hedging_pnl = 0
    for t in range(len(trajectory['positions']) - 1):
        position = trajectory['positions'][t]
        price_change = trajectory['stock_prices'][t+1] - trajectory['stock_prices'][t]
        hedging_pnl += position * price_change * env.number_of_shares
    
    # Calculate normalized return
    final_value = option_payoff + hedging_pnl
    normalized_return = (final_value - initial_investment) / initial_investment
    
    # Store results
    results['returns'].append(normalized_return)
    results['final_pnls'].append(final_value - initial_investment)
    results['option_payoffs'].append(option_payoff)
    results['hedging_pnls'].append(hedging_pnl)
    results['premiums_paid'].append(initial_investment)
    results['tickers'].append(env.ticker)
    results['initial_expiry_days'].append(initial_expiry)
    results['optimal_max_returns'].append(max_return)
    results['optimal_min_returns'].append(min_return)
    
    if (episode + 1) % 100 == 0:
        print(f"Completed {episode + 1}/{num_episodes} episodes")

# Convert to arrays
returns = np.array(results['returns'])
optimal_max = np.array(results['optimal_max_returns'])
optimal_min = np.array(results['optimal_min_returns'])

# Create visualizations
fig = plt.figure(figsize=(16, 10))

# 1. Returns Distribution
ax1 = plt.subplot(2, 3, 1)
plt.hist(returns * 100, bins=50, alpha=0.7, color='blue', edgecolor='black')
plt.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break-even')
mean_return = returns.mean() * 100
plt.axvline(x=mean_return, color='green', linestyle='-', linewidth=2, label=f'Mean: {mean_return:.1f}%')
plt.xlabel('Return (%)')
plt.ylabel('Frequency')
plt.title('Distribution of Returns')
plt.legend()

# 2. P&L Components Analysis
ax2 = plt.subplot(2, 3, 2)
option_payoff_pct = np.mean(results['option_payoffs']) / np.mean(results['premiums_paid']) * 100
hedging_pnl_pct = np.mean(results['hedging_pnls']) / np.mean(results['premiums_paid']) * 100
net_return_pct = returns.mean() * 100

components = ['Option\nPayoff', 'Hedging\nP&L', 'Net\nReturn']
values = [option_payoff_pct, hedging_pnl_pct, net_return_pct]
colors = ['green', 'orange', 'purple']

bars = plt.bar(components, values, color=colors, alpha=0.7)
plt.ylabel('% of Premium Paid')
plt.title('P&L Components (as % of Premium)')
plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
plt.axhline(y=-100, color='red', linestyle='--', linewidth=1, label='Total Loss')

for bar, val in zip(bars, values):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + np.sign(val)*5, 
             f'{val:.1f}%', ha='center', va='bottom' if val > 0 else 'top')

# 3. Returns by Initial Expiry Days
ax3 = plt.subplot(2, 3, 3)
expiry_days = np.array(results['initial_expiry_days'])
unique_expiries = sorted(set(expiry_days))

expiry_groups = {}
for exp in unique_expiries:
    mask = expiry_days == exp
    if mask.sum() > 0:
        expiry_groups[exp] = returns[mask] * 100

box_data = [expiry_groups[exp] for exp in sorted(expiry_groups.keys())]
box_labels = [f'{exp}d' for exp in sorted(expiry_groups.keys())]
plt.boxplot(box_data, tick_labels=box_labels)  # Using tick_labels instead of labels
plt.xlabel('Initial Days to Expiry')
plt.ylabel('Return (%)')
plt.title('Returns by Option Expiry Period')
plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)

# 4. Rolling Sharpe Ratio (CORRECTED)
ax4 = plt.subplot(2, 3, 4)
window = 20
# Correct Sharpe calculation: mean/std without annualization for episode-based returns
rolling_returns = pd.Series(returns)
rolling_mean = rolling_returns.rolling(window).mean()
rolling_std = rolling_returns.rolling(window).std()
rolling_sharpe = rolling_mean / (rolling_std + 1e-8)  # Simple Sharpe, no annualization

plt.plot(rolling_sharpe.dropna(), color='purple', linewidth=2)
plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)
plt.axhline(y=1, color='green', linestyle='--', alpha=0.5, label='Sharpe = 1')
plt.xlabel('Episode')
plt.ylabel('Rolling Sharpe Ratio')
plt.title(f'Rolling Sharpe Ratio ({window}-episode window)')
plt.legend()
plt.ylim(-2, 3)  # Reasonable range for Sharpe

# 5. Model vs Optimal Performance
ax5 = plt.subplot(2, 3, 5)
episodes = np.arange(len(returns))

# 5. Model vs Optimal Performance (UPDATED)
ax5 = plt.subplot(2, 3, 5)
episodes = np.arange(len(returns))

# Add moving averages for clarity
window = 20
model_ma = pd.Series(returns * 100).rolling(window).mean()
max_ma = pd.Series(optimal_max * 100).rolling(window).mean()
min_ma = pd.Series(optimal_min * 100).rolling(window).mean()

plt.plot(episodes, model_ma, 'b-', linewidth=2, label=f'Model MA({window})')
plt.plot(episodes, max_ma, 'g--', linewidth=2, label=f'Max MA({window})')
plt.plot(episodes, min_ma, 'r--', linewidth=2, label=f'Min MA({window})')

plt.xlabel('Episode')
plt.ylabel('Return (%)')
plt.title('Model vs Optimal Performance')
plt.legend(loc='upper right')
plt.grid(True, alpha=0.3)
plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)

# 6. Performance Summary Table
ax6 = plt.subplot(2, 3, 6)
ax6.axis('off')

# Calculate CORRECTED metrics
simple_sharpe = returns.mean() / (returns.std() + 1e-8)
downside_std = returns[returns < 0].std() if (returns < 0).any() else 1e-8
sortino = returns.mean() / downside_std

# Max drawdown calculation
cumsum = pd.Series(returns).cumsum()
cummax = cumsum.cummax()
max_dd = (cumsum - cummax).min()

win_rate = (returns > 0).mean()

# Create summary table
summary_data = [
    ['Metric', 'Value'],
    ['Mean Return', f'{returns.mean()*100:.1f}%'],
    ['Standard Deviation', f'{returns.std()*100:.1f}%'],
    ['Sharpe Ratio', f'{simple_sharpe:.2f}'],
    ['Sortino Ratio', f'{sortino:.2f}'],
    ['Max Drawdown', f'{max_dd*100:.1f}%'],
    ['Win Rate', f'{win_rate*100:.1f}%'],
    ['Avg Win', f'{returns[returns>0].mean()*100:.1f}%' if (returns > 0).any() else 'N/A'],
    ['Avg Loss', f'{returns[returns<0].mean()*100:.1f}%' if (returns < 0).any() else 'N/A'],
    ['Best Return', f'{returns.max()*100:.1f}%'],
    ['Worst Return', f'{returns.min()*100:.1f}%']
]

table = ax6.table(cellText=summary_data[1:], colLabels=summary_data[0],
                  cellLoc='left', loc='center', 
                  colWidths=[0.6, 0.4])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.5)

for i in range(len(summary_data)):
    if i == 0:
        table[(i, 0)].set_facecolor('#40466e')
        table[(i, 1)].set_facecolor('#40466e')
        table[(i, 0)].set_text_props(weight='bold', color='white')
        table[(i, 1)].set_text_props(weight='bold', color='white')
    else:
        table[(i, 0)].set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')
        table[(i, 1)].set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')

plt.title('Performance Metrics Summary')

plt.suptitle('MCPG Option Hedging Analysis', fontsize=16)
plt.tight_layout()
plt.show()

# Print analysis
print(f"\nPerformance vs Optimal:")
print(f"  Model Avg Return: {returns.mean()*100:.1f}%")
print(f"  Optimal Max Avg Return: {optimal_max.mean()*100:.1f}%")
print(f"  Optimal Min Avg Return: {optimal_min.mean()*100:.1f}%")
print(f"  Model captures {returns.mean()/optimal_max.mean()*100:.1f}% of maximum possible return")