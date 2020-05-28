# -*- coding: utf-8 -*-
"""Venmo_Q1_4.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1PjML6tFy5VBTVZU-Y6EjVifDQEdc7SgP
"""

# Import package
import findspark
findspark.init()
import pyspark
from pyspark import SparkConf, SparkContext
import pandas as pd
from pyspark.sql.functions import expr
import pyspark.sql.functions as F
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType, ArrayType, IntegerType, FloatType
from pyspark.sql.functions import *
from pyspark.sql.functions import count
from pyspark.sql import Window
from pyspark.sql.functions import concat
from pyspark.sql import SparkSession
import pandas as pd
import matplotlib.pyplot as plt

# Add a file path for Java Home
import os
os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/adoptopenjdk-8.jdk/Contents/Home"

# Import Venmo data
MAX_MEMORY = '12g'
spark = SparkSession\
        .builder\
        .appName('venmo')\
        .config("spark.driver.memory", MAX_MEMORY) \
        .getOrCreate()
venmo=spark.read.parquet('VenmoSample.snappy.parquet')
venmo.show(5)

"""**Text Analytics**

** Use the text dictionary and the emoji dictionary to classify Venmo’s transactions in the sample dataset.*
"""

# Import the stacked dictionary contained all the text and emojis
dictionary=spark.read.csv('text_all.csv',header=True)
dictionary.show(5)

# Create lists for dictionary
People=[row[0] for row in dictionary.select(dictionary.columns[0]).collect()]
Food=[row[0] for row in dictionary.select(dictionary.columns[1]).collect()]
Event=[row[0] for row in dictionary.select(dictionary.columns[2]).collect()]
Activity=[row[0] for row in dictionary.select(dictionary.columns[3]).collect()]
Travel=[row[0] for row in dictionary.select(dictionary.columns[4]).collect()]
Trans=[row[0] for row in dictionary.select(dictionary.columns[5]).collect()]
Utility=[row[0] for row in dictionary.select(dictionary.columns[6]).collect()]
Cash=[row[0] for row in dictionary.select(dictionary.columns[7]).collect()]
Illegal=[row[0] for row in dictionary.select(dictionary.columns[8]).collect()]

# Define a function to classify the words
def word_type(x):
    categories=[]
    for var in x:
        if var in People:
            categories.append('People')
        if var in Food:
            categories.append('Food')
        if var in Event:
            categories.append('Event')
        if var in Activity:
            categories.append('Activity')
        if var in Travel:
            categories.append('Travel')
        if var in Trans:
            categories.append('Trans')
        if var in Utility:
            categories.append('Utility')
        if var in Cash:
            categories.append('Cash')
        if var in Illegal:
            categories.append('Illegal')
    return categories

# Tokenized the description of Venmo data
from pyspark.ml.feature import Tokenizer
tokenizer = Tokenizer(inputCol="description", outputCol="words") 
tokenized = tokenizer.transform(venmo)
tokenized.show(5)

# Use withColumn to add category
word_type_udf=F.udf(lambda y: word_type(y), ArrayType(StringType()))

tokenized=tokenized.withColumn('category',word_type_udf(F.col('words')))
tokenized.show(5)

"""** the top 5 most popular emoji? 🍕🍻🍴🍺⛽*

** the top three most popular emoji categories: Food, People, Activity*
"""

# Create two columns save the emojis and words seperately
import emoji
is_emoji = lambda x: [val for val in x if val in emoji.UNICODE_EMOJI ]
is_not_emoji = lambda x: [val for val in x if val not in emoji.UNICODE_EMOJI ]
is_emoji_udf = udf(lambda z: is_emoji(z), ArrayType(StringType()))
is_not_emoji_udf = udf(lambda z: is_not_emoji(z), ArrayType(StringType()))
description_list=tokenized.select('user1','user2','datetime', is_emoji_udf('words').alias('emojis'),is_not_emoji_udf('words').alias('words'))

description_list.show(5)

# Define a function to see whether the words is a empty list, if yes, then it means this description only contains emoji
def emoji_only(x):
    list_length=len(x)
    if list_length:
        return 0
    else:
        return 1

emoji_only_udf=udf(lambda z:emoji_only(z),IntegerType())
description_list.select('user1','user2','datetime','emojis','words',emoji_only_udf('words').alias('emoji_only')).show()

emoji_only_table=description_list.select('user1','user2','datetime','emojis','words',emoji_only_udf('words').alias('emoji_only'))

emoji_only_table.where('emoji_only=1').count()

# The percentage of emoji only transaction
1027597/description_list.count()

"""Top 5 emojis"""

is_emoji = lambda x: [val for val in x if val in emoji.UNICODE_EMOJI ]
is_emoji_udf = udf(lambda z: is_emoji(z), StringType())
emoji_string=tokenized.select('user1','user2','datetime', is_emoji_udf('words').alias('emojis'))

emoji_string.show(5)

emoji_string.createOrReplaceTempView('emoji_string')

# Find the top 5 popolar emojis
spark.sql('''select emojis, count(emojis) from emoji_string where emojis is not null group by emojis order by count(emojis) desc''').show(6)

"""Top 3 category"""

# Use the categorize function again to find the category for emojis
emoji_string_category=emoji_string.withColumn('category',word_type_udf(F.col('emojis')))

# Remove the rows with empty category
emoji_string_category=emoji_string_category.filter(F.size('category') > 0) # F.size can be used to see the length of column
emoji_string_category.show()

# Find the top 3 category with emojis
emoji_string_category.createOrReplaceTempView('emoji_string_category')
spark.sql('''select category, count(category) from emoji_string_category group by category order by count(category) desc''').show(3)

"""** create a variable to indicate their spending behavior profile*"""

user_category=tokenized.select('user1','user2','datetime','category')
user_category.show(5)

# Remove the rows with no category 
user_category=user_category.filter(F.size('category')>0)

user_category.count()

# Order by the user id and category
user_category.createOrReplaceTempView('user_category')
user_category_order=spark.sql('''select * from user_category order by user1,category''')

user_category_order.show(5)

user1_category_order=user_category_order.select('user1', F.explode('category').alias("category"))\
                                       .groupBy('user1','category')\
                                       .count()\
                                       .select('user1','category', 'count',F.sum('count').over(Window.partitionBy("user1")).alias('total_count'))\
                                       .sort('user1', 'category')

# Calculate the proprotion of each category
user1_category_order=user1_category_order.select('user1','category',(100*(round(((col("count") /col("total_count"))),2))).alias("proportion_%"))

# Pivot the table
user1_category_order=user1_category_order.groupBy('user1')\
                       .pivot("category").sum("proportion_%").sort("user1")
user1_category_order.show()

"""**explore how a user’s spending profile is evolving over her lifetime in Venmo, starting from 0 up to 12.*"""

# Create table for user profile every month

# Break the datetime into months
user_profile=user_category_order.selectExpr('user1',"CAST( MONTHS_BETWEEN(datetime, FIRST_VALUE(datetime) OVER (PARTITION BY user1 ORDER BY datetime)) as INT) as month",'category')
# Filter months that are less than 12
user_profile=user_profile.filter(F.col('month')<=12).sort('month')

# Explode the category
user_profile=user_profile.select('user1','month', F.explode('category').alias("category"))\
                         .groupBy('user1','month','category')\
                         .count()\
                         .select('user1','month','category','count', F.sum('count').over(Window.partitionBy("user1",'month')).alias('total_count'))\
                                       .sort('user1', 'month','category')

# Calculate the proportion
user_profile=user_profile.select("user1","month",'category','count','total_count',(100*(round(((col("count") /col("total_count"))),2))).alias("proportion_%"))
user_profile=user_profile.select("user1","month",'category',"proportion_%")

# Pivot the table
user_profile_yearly = user_profile.groupBy('user1','month')\
                       .pivot("category").sum("proportion_%").sort("user1",'month')
user_profile_yearly.repartition(1).write.mode('overwrite').parquet("/Users/calvin/Desktop/Spring Quarter/Big data/Homework 2/user_profile_yearly.parquet")

# Calculate the mean and standard deviation
profile_count=tokenized.selectExpr('user1',"CAST( MONTHS_BETWEEN(datetime, FIRST_VALUE(datetime) OVER (PARTITION BY user1 ORDER BY datetime)) as INT) as month",'category').sort('user1','month')
profile_count=profile_count.filter(F.col('month')<=12)

profile_count=profile_count.select('user1','month',F.explode('category').alias("category"))\
                           .groupBy('user1','month','category')\
                           .count()\
                           .select('user1','month','category','count')

profile_count.createOrReplaceTempView('profile_count')
profile_mean=spark.sql('''select month, category, avg(count), stddev(count) from profile_count where month<=12 group by category, month order by category, month''')
profile_mean_pd=profile_mean.toPandas()

profile_mean_pd.head(5)

venmo_plot=profile_mean_pd.rename(columns={'avg(count)':'avg','stddev_samp(CAST(count AS DOUBLE))':'sd'})
venmo_plot['sd_2']=2*venmo_plot['sd']

venmo_plot.head()

fig, ax = plt.subplots(figsize=(20,10))    # 1

for key, group in venmo_plot.groupby('category'):
    group.plot('avg', 'month', xerr='sd_2', label=key, ax=ax)   # 2

plt.show()

