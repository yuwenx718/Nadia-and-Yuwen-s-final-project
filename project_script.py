import os
import requests
import pandas as pd
import numpy as np
import us
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from datetime import datetime

# Download the data from https://api.covidtracking.com
path = os.path.abspath(os.path.dirname(__file__))
api = r'https://api.covidtracking.com/v1/states/daily.csv'

def get_statement(api, fname, path):
    response = requests.get(api)
    assert(fname.endswith('.csv')), 'Incorrect file type in get_statement, expected csv, got: {}'.format(api)
    with open(os.path.join(path, fname), 'wb') as file:
        file.write(response.content)

go_online = True # Change True if the file(s) not yet in the folder (see files)
fname = [] 
fname = api.split('/')[-1]
if go_online:
    get_statement(api, fname, path)
    
# Compare table from NGA and expire to get the latest reopening date
files = ['state_expire_multistate.csv', 'table.csv', 'daily.csv']
keys = ['expire', 'nga', 'daily']
files = {k:v for k,v in zip(keys, files)}
 
def compare_date(key1, key2):
    dfs = []
    for k in files:
        if k in [key1, key2]:
            df = pd.read_csv(files[k]) 
            dfs.append(df)
    
    df = dfs[0].merge(dfs[1], on=['state'], how='left', 
                  indicator='exists')

    df['expire_date'] = df['expire_date'].map('{} 20'.format)
    
    for col in ['expire_date', 'Reopen date']:
        df[col] = pd.to_datetime(df[col], errors = 'coerce')
  
    df['policy_date'] = np.where((df['Reopen date'] > df['expire_date']), df['Reopen date'], df['expire_date'])
    df = df[['state', 'policy_date']].drop_duplicates(subset=['state'])
    return df

df_reopening = compare_date('expire', 'nga')     
df_reopening.to_csv('state_reopeningdate.csv', index=False)
    
# Read US Governor party csv data from github 
us_party = pd.read_csv('https://raw.githubusercontent.com/CivilServiceUSA/us-governors/master/us-governors/data/us-governors.csv')
us_party = us_party[['state_name', 'state_code', 'party']]
us_party.to_csv('us_party.csv', index=False)    
    
# Create dataframe containing state_id    
abbr = [state.abbr for state in us.states.STATES]
state = [state.name for state in us.states.STATES]
states_dict = {k:v for k,v in zip(abbr, state)}
states = pd.DataFrame(states_dict.items(), columns=['state_id', 'state'])
    
# Open daily data, create new column state for abbreviation
df_covid = pd.read_csv(files['daily'])
df_covid = df_covid[['date', 'state', 'positive', 'probableCases', 'negative']]
df_covid['date']=pd.to_datetime(df_covid['date'], format='%Y%m%d', errors = 'coerce')

df_covid = df_covid.merge(states, left_on=['state'], right_on=['state_id'], how='outer',
                          indicator=True)

# Merge with reopening policy date
df = df_covid.merge(df_reopening, left_on=['state_y'], right_on=['state'], how='outer',
                          indicator=False)

# Merge with governor's party 
df = df.merge(us_party, left_on=['state_y'], right_on=['state_name'], how='left', indicator=False)
col_drop = ['state_x', 'state_id', 'state_y', 'state', '_merge']
df.drop([col for col in df.columns if col in col_drop], axis=1, inplace=True)
df.to_csv('data.csv', index=False)    
    
# Creating Graphs
# Set earliest(1 March) and latest(30 November) date for each state

# 1) Average Comparison of The Number of Cases between Republican and Democrat States
df['tot_avg_party'] = df.groupby(['date', 'party'])['positive'].transform('mean')
df['new_cases'] = df.groupby(['state_name'])['positive'].diff(-1)
df['new_case_mean_party'] = df.groupby(['date', 'party'])['new_cases'].transform('mean')
df['new_case_total'] = df.groupby(['date'])['new_cases'].transform('mean')
df['after_policy'] = (df['date'] > df['policy_date']).astype(int)
df['new_case_after'] = df.groupby(['state_name', 'after_policy'])['new_cases'].transform('mean')

# Add bar chart for average daily cases overall
def plot_cases_by_party(data, fname):
    fig, ax = plt.subplots(figsize=(15,7))
    ax.set_title('Average Number of Covid-19 Daily Cases', fontsize=16)
    ax.set_xlabel('Date', fontsize=14)
    ax.set_ylabel('New Cases', fontsize=14)
    ax.bar('date', 'new_case_total', data = data, color='lightgray')
    dstart = datetime(2020,4,1)
    dend = datetime(2020,11,30)
    ax.set_xlim([dstart, dend])
    ax2 = ax.twinx()
    ax2 = sns.lineplot(x='date', y='new_case_mean_party', hue='party', data = data, palette=['r', 'b'])
    ax2.set_yticks([])
    ax2.set_ylabel('')
    legend = ax2.legend(loc='best')
    legend.texts[0].set_text('Political Party')
    plt.savefig(fname)
    plt.show()
    
plot_cases_by_party(df, 'average_by_party.png')

# 2) Show bar chart by state with highest average number of Covid-19 cases after reopening
df_overall = df[['state_name', 'new_case_after', 'after_policy', 'party']].drop_duplicates()
df_overall = df_overall[df_overall['after_policy']==1].nlargest(25, 'new_case_after')

# Dictionary with key state
def bar_by_party(data, fname):
    fig, ax = plt.subplots(figsize=(15,8))
    ax.set_title('Average Number of New Cases of 25 States with Highest Cases after Reopening', fontsize=16)
    ax.set_xlabel('Total Cases', fontsize=14)
    ax.set_ylabel('State', fontsize=14)
    y_pos = np.arange(len(df_overall['state_name']))
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_overall['state_name'])
    ax.invert_yaxis()
    
    top25_state = [r for r in df_overall['state_name']]
    top25_party = [r for r in df_overall['party']]
    top25_dict = {k:v for k,v in zip(top25_state, top25_party)}

    clr = []
    for v in top25_dict.values(): # keys are the names of the boys
        if v == 'republican':
            clr.append('indianred')
        else:
            clr.append('darkblue')
            
    ax.barh(y_pos, data['new_case_after'], color=clr, align='center')
    red_patch = mpatches.Patch(color='indianred', label='Republican')
    blue_patch = mpatches.Patch(color='darkblue', label='Democrat')
    plt.legend(handles=[red_patch, blue_patch])
    plt.savefig(fname)
    plt.show()

bar_by_party(df_overall, 'top25_states_highest_cases.png')

# 2) Average comparison of policy date between republican and democrat states


